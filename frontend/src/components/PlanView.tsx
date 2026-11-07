import type { StudyPlan } from "../api/client";

const KIND_LABEL: Record<string, string> = {
  review_flashcards: "🃏 Flashcards",
  quiz: "❓ Quiz",
  study: "📖 Study",
  rest: "☕ Rest",
};

export function PlanView({ plan }: { plan: StudyPlan }) {
  return (
    <div className="plan">
      <p>{plan.summary}</p>
      {plan.days.map((d) => (
        <div key={d.date} className="day">
          <strong>{new Date(d.date + "T00:00").toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}</strong>
          <ul>
            {d.tasks.map((t, i) => (
              <li key={i}>
                {KIND_LABEL[t.kind] ?? t.kind} · {t.minutes} min{t.concept ? ` · ${t.concept}` : ""}
                <div className="muted small">{t.note}</div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
