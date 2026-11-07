"""End-to-end smoke test against a running backend + real Supabase + real OpenAI.

Usage (from backend/, with .env filled in and the API running on :8000):
    python scripts/smoke_test.py                 # uses a built-in sample lecture
    python scripts/smoke_test.py --file my.pdf   # test with your own material
    python scripts/smoke_test.py --keep          # don't delete the test user afterwards

It creates a throwaway confirmed user via the Supabase admin API, exercises every
feature, prints a pass/fail line per step and deletes the user (all data cascades).
"""

import argparse
import json
import sys
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings  # noqa: E402
from supabase import create_client  # noqa: E402

SAMPLE = """# Lecture 3: Photosynthesis

Photosynthesis is the process by which plants, algae and some bacteria convert light energy
into chemical energy stored in glucose. It takes place in the chloroplasts, organelles that
contain the green pigment chlorophyll.

## Light-dependent reactions
These occur in the thylakoid membranes. Light excites electrons in chlorophyll; water is split
(photolysis), releasing oxygen as a by-product. The energy is captured as ATP and NADPH.

## Calvin cycle (light-independent reactions)
In the stroma, the enzyme RuBisCO fixes carbon dioxide onto ribulose bisphosphate (RuBP).
Using ATP and NADPH from the light reactions, the cycle produces G3P, which is used to build
glucose. The overall equation is 6CO2 + 6H2O + light -> C6H12O6 + 6O2.

## Limiting factors
The rate of photosynthesis is limited by light intensity, carbon dioxide concentration and
temperature. Above an optimum temperature, enzymes such as RuBisCO denature.
"""

results: list[tuple[str, bool]] = []


def step(name: str):
    def deco(fn):
        def run(*a, **kw):
            t = time.time()
            try:
                out = fn(*a, **kw)
                print(f"  ✓ {name} ({time.time() - t:.1f}s)")
                results.append((name, True))
                return out
            except Exception as e:  # report and keep going where possible
                print(f"  ✗ {name}: {e}")
                results.append((name, False))
                return None
        return run
    return deco


def check(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)


def stream_chat(client: httpx.Client, course_id: str, message: str) -> list[tuple[str, dict]]:
    events, name = [], None
    with client.stream("POST", f"/api/courses/{course_id}/chat", json={"message": message},
                       timeout=180) as r:
        check(r.status_code == 200, f"HTTP {r.status_code}: {r.read().decode()[:300]}")
        for line in r.iter_lines():
            if line.startswith("event:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and name:
                events.append((name, json.loads(line.split(":", 1)[1].strip() or "{}")))
                name = None
    return events


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--file", type=Path, help="Course material to upload instead of the sample")
    ap.add_argument("--keep", action="store_true", help="Keep the test user and its data")
    args = ap.parse_args()

    s = get_settings()
    admin = create_client(s.supabase_url, s.supabase_service_role_key)
    email = f"smoke-{uuid.uuid4().hex[:8]}@studeasy.test"
    password = uuid.uuid4().hex
    user_id = None

    print(f"Studeasy smoke test against {args.api}\n")
    try:
        @step("API is up")
        def health():
            r = httpx.get(f"{args.api}/api/health", timeout=10)
            check(r.status_code == 200, f"HTTP {r.status_code}")

        health()
        if not results[-1][1]:
            print("\nStart the API first: uvicorn app.main:app --reload")
            return 1

        @step("Create test user and sign in (Supabase Auth)")
        def login():
            nonlocal user_id
            u = admin.auth.admin.create_user(
                {"email": email, "password": password, "email_confirm": True}
            )
            user_id = u.user.id
            session = create_client(s.supabase_url, s.supabase_service_role_key).auth \
                .sign_in_with_password({"email": email, "password": password}).session
            return session.access_token

        token = login()
        if not token:
            return 1
        api = httpx.Client(base_url=args.api, headers={"Authorization": f"Bearer {token}"},
                           timeout=120)

        @step("Reject request without token")
        def unauth():
            check(httpx.get(f"{args.api}/api/courses").status_code == 401, "expected 401")

        unauth()

        @step("Create course")
        def course():
            r = api.post("/api/courses", json={"name": "Biology 101 (smoke test)"})
            check(r.status_code == 201, r.text)
            return r.json()["id"]

        course_id = course()
        if not course_id:
            return 1

        @step("Upload material and wait for ingestion")
        def upload():
            if args.file:
                files = [("files", (args.file.name, args.file.read_bytes()))]
            else:
                files = [("files", ("photosynthesis.md", SAMPLE.encode()))]
            r = api.post(f"/api/courses/{course_id}/documents", files=files)
            check(r.status_code == 202, r.text)
            deadline = time.time() + 240
            while time.time() < deadline:
                docs = api.get(f"/api/courses/{course_id}/documents").json()
                if all(d["status"] != "processing" for d in docs):
                    failed = [d for d in docs if d["status"] == "failed"]
                    check(not failed, f"ingestion failed: {failed[0]['error'] if failed else ''}")
                    print(f"      {sum(d['chunk_count'] for d in docs)} chunks stored")
                    return
                time.sleep(2)
            raise AssertionError("still processing after 4 minutes")

        upload()

        @step("Content agent extracted concepts (mastery map)")
        def concepts():
            m = api.get(f"/api/courses/{course_id}/mastery").json()
            check(len(m) > 0, "no concepts")
            print(f"      {', '.join(c['concept'] for c in m[:8])}")

        concepts()

        @step("Chat: tutor explains with sources + verification (SSE)")
        def chat_explain():
            ev = stream_chat(api, course_id, "Can you explain what the Calvin cycle does?")
            kinds = [e for e, _ in ev]
            intent = next(d for e, d in ev if e == "intent")
            check(intent["intent"] == "explain", f"routed to {intent['intent']}")
            check("sources" in kinds, "no sources event")
            answer = "".join(d["text"] for e, d in ev if e == "token")
            check(len(answer) > 20, "empty answer")
            check(kinds[-1] == "done", f"stream ended with {kinds[-1]}")
            ver = next((d for e, d in ev if e == "verification"), None)
            print(f"      answer: {answer[:160].replace(chr(10), ' ')}...")
            print(f"      verification: {ver}")

        chat_explain()

        @step("Chat: 'quiz me' routes to the quiz master")
        def chat_quiz():
            ev = stream_chat(api, course_id, "Quiz me on photosynthesis please")
            quiz = next((d for e, d in ev if e == "quiz"), None)
            err = next((d for e, d in ev if e == "error"), None)
            check(quiz is not None, f"no quiz event (error: {err})")
            print(f"      {len(quiz['questions'])} questions generated")

        chat_quiz()

        @step("Chat: study question routes to the planner")
        def chat_plan():
            ev = stream_chat(api, course_id, "What should I study this week?")
            check(any(e == "plan" for e, _ in ev), f"events: {[e for e, _ in ev]}")

        chat_plan()

        @step("Generate quiz with all question types")
        def quiz():
            r = api.post(f"/api/courses/{course_id}/quizzes",
                         json={"types": ["multiple_choice", "true_false", "open"], "count": 3})
            check(r.status_code == 201, r.text)
            q = r.json()
            check(q["questions"], "no questions")
            check(all("answer" not in x for x in q["questions"]), "answers leaked to client")
            return q

        q = quiz()

        @step("Grade answers (exact + LLM-graded open answer)")
        def answer():
            for question in q["questions"]:
                response = {
                    "multiple_choice": (question["options"] or ["?"])[0],
                    "true_false": "true",
                    "open": "It uses ATP and NADPH to fix CO2 into sugar with RuBisCO.",
                }[question["type"]]
                r = api.post(f"/api/quizzes/{q['id']}/answers",
                             json={"question_id": question["id"], "response": response})
                check(r.status_code == 200, r.text)
                res = r.json()
                print(f"      [{question['type']}] score {res['score']:.2f} - {res['feedback'][:90]}")

        if q:
            answer()

        @step("Flashcards: generate, list due, SM-2 review")
        def flashcards():
            r = api.post(f"/api/courses/{course_id}/flashcards", json={"count": 3})
            check(r.status_code == 201, r.text)
            due = api.get(f"/api/courses/{course_id}/flashcards/due").json()
            check(len(due) >= 1, "no due cards")
            card = api.post(f"/api/flashcards/{due[0]['id']}/review", json={"quality": 4}).json()
            check(card["interval"] == 1 and card["repetitions"] == 1, f"unexpected SM-2 state {card}")

        flashcards()

        @step("Exam + study plan")
        def plan():
            exam_date = (date.today() + timedelta(days=4)).isoformat()
            r = api.post(f"/api/courses/{course_id}/exams",
                         json={"title": "Midterm", "exam_date": exam_date})
            check(r.status_code == 201, r.text)
            p = api.get(f"/api/courses/{course_id}/plan", params={"daily_minutes": 45}).json()
            check(len(p["days"]) == 4, f"expected 4 days, got {len(p.get('days', []))}")
            print(f"      {p['summary'][:160]}")

        plan()

        @step("Mastery updated by answers and reviews")
        def mastery_updated():
            m = api.get(f"/api/courses/{course_id}/mastery").json()
            check(any(c["attempts"] > 0 for c in m), "no attempts recorded")

        mastery_updated()

        if api.get("/api/features").json().get("reels"):
            @step("Reels: blocked until the student opts in")
            def reels_optin():
                r = api.get(f"/api/courses/{course_id}/reels/feed")
                check(r.status_code == 403, f"expected 403, got {r.status_code}")
                r = api.patch("/api/me/preferences", json={"reels_enabled": True})
                check(r.status_code == 200 and r.json()["reels_enabled"], r.text)

            reels_optin()

            @step("Reels: adaptive feed generated on demand")
            def reels_feed():
                r = api.get(f"/api/courses/{course_id}/reels/feed", timeout=180)
                check(r.status_code == 200, r.text)
                items = r.json()["items"]
                check(items, "empty feed")
                print(f"      {[i['type'] for i in items]}")
                first = next(i for i in items if i["type"] == "explainer")
                print(f"      hook: {first['content']['hook']}")
                return items

            items = reels_feed() or []

            @step("Reels: record view + answer a quiz reel")
            def reels_interact():
                reel = next(i for i in items if i["type"] != "break")
                r = api.post(f"/api/reels/{reel['id']}/view",
                             json={"watch_ms": 4200, "completed": True})
                check(r.status_code == 204, r.text)
                quiz_reel = next((i for i in items if i["type"] == "quiz"), None)
                if quiz_reel:
                    r = api.post(f"/api/reels/{quiz_reel['id']}/answer",
                                 json={"response": quiz_reel["content"]["options"][0]})
                    check(r.status_code == 200, r.text)
                    print(f"      quiz: correct={r.json()['correct']}")

            if items:
                reels_interact()
    finally:
        if user_id and not args.keep:
            admin.auth.admin.delete_user(user_id)
            print("\n  (test user and all its data deleted)")
        elif user_id:
            print(f"\n  Kept test user {email} / {password}")

    passed = sum(ok for _, ok in results)
    print(f"\n{passed}/{len(results)} steps passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
