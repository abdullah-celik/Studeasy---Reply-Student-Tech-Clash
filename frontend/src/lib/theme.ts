import { useEffect, useState } from "react";
import { store } from "./format";

export type ThemePref = "system" | "light" | "dark";
const KEY = "studeasy:theme";
const media = () => window.matchMedia("(prefers-color-scheme: dark)");

/** Same logic as the inline script in index.html (runs before first paint). */
function apply(pref: ThemePref) {
  const root = document.documentElement;
  if (pref === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", pref);
}

export function useTheme() {
  const [pref, setPrefState] = useState<ThemePref>(() => (store.get(KEY) as ThemePref) || "system");
  const [systemDark, setSystemDark] = useState(() => media().matches);

  useEffect(() => {
    const m = media();
    const on = () => setSystemDark(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);

  useEffect(() => apply(pref), [pref]);

  function setPref(p: ThemePref) {
    store.set(KEY, p);
    setPrefState(p);
  }

  const effective: "light" | "dark" = pref === "system" ? (systemDark ? "dark" : "light") : pref;
  return { pref, setPref, effective, toggle: () => setPref(effective === "dark" ? "light" : "dark") };
}

export type Theme = ReturnType<typeof useTheme>;
