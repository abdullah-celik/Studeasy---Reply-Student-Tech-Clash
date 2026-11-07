import { useCallback, useEffect, useState } from "react";
import type { Mode } from "../modes/types";

/**
 * Tiny URL router so a refresh (or a shared link) lands where the student was:
 *   /                                  dashboard
 *   /settings                          settings
 *   /courses/<id>[/<mode>][?item=<id>] a course, its mode and the open chat/quiz/deck/plan/reel
 * Static hosts must serve index.html for unknown paths (Vite dev does; Cloudflare Pages
 * does for projects without a 404.html).
 */
export type Route =
  | { name: "home" }
  | { name: "settings" }
  | { name: "course"; courseId: string; mode: Mode | null; item: string | null };

const MODES: Mode[] = ["chat", "quiz", "flashcards", "reels", "plan"];

export function parse(loc: Location = window.location): Route {
  const parts = loc.pathname.split("/").filter(Boolean).map(decodeURIComponent);
  if (parts[0] === "settings") return { name: "settings" };
  if (parts[0] === "courses" && parts[1]) {
    const mode = MODES.includes(parts[2] as Mode) ? (parts[2] as Mode) : null;
    return { name: "course", courseId: parts[1], mode, item: new URLSearchParams(loc.search).get("item") };
  }
  return { name: "home" };
}

export function toPath(r: Route): string {
  if (r.name === "settings") return "/settings";
  if (r.name === "course") {
    let p = `/courses/${encodeURIComponent(r.courseId)}`;
    if (r.mode) p += `/${r.mode}`;
    if (r.item) p += `?item=${encodeURIComponent(r.item)}`;
    return p;
  }
  return "/";
}

export function useRoute() {
  const [route, setRoute] = useState<Route>(() => parse());

  useEffect(() => {
    const on = () => setRoute(parse());
    window.addEventListener("popstate", on);
    return () => window.removeEventListener("popstate", on);
  }, []);

  /** push: a new page (back button returns here); replace: same page, updated details. */
  const navigate = useCallback((r: Route, how: "push" | "replace" = "push") => {
    const path = toPath(r);
    if (path !== window.location.pathname + window.location.search) {
      window.history[how === "push" ? "pushState" : "replaceState"](null, "", path);
    }
    setRoute(r);
  }, []);

  return { route, navigate };
}
