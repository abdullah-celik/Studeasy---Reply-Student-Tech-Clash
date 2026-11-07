import { useEffect, useRef, useState } from "react";

const KEY = "studeasy:splash-seen";
const SRC = "/splash.gif"; // public/, preloaded in index.html
const PLAY_MS = 2200; // length of the GIF (it plays once and ends fully transparent)
const LOAD_TIMEOUT_MS = 3000;

function shouldShow(): boolean {
  try {
    if (sessionStorage.getItem(KEY)) return false;
  } catch {
    /* storage blocked: still show it */
  }
  return !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Intro shown once per browser tab: the wizard's window splits open and the app
 * appears in the gap. The GIF's opening is transparent, so the page shows through it.
 */
export function Splash() {
  const [show, setShow] = useState(shouldShow);
  const [loaded, setLoaded] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  function finish() {
    try {
      sessionStorage.setItem(KEY, "1");
    } catch {
      /* ignore */
    }
    setShow(false);
  }

  // If the GIF is slow to arrive, don't keep the student waiting: fade the curtain away.
  useEffect(() => {
    if (!show || loaded) return;
    const t = window.setTimeout(() => setLeaving(true), LOAD_TIMEOUT_MS);
    return () => window.clearTimeout(t);
  }, [show, loaded]);

  useEffect(() => {
    if (!leaving) return;
    const t = window.setTimeout(finish, 300);
    return () => window.clearTimeout(t);
  }, [leaving]);

  useEffect(() => {
    if (!show) return;
    const skip = () => setLeaving(true);
    window.addEventListener("keydown", skip);
    return () => {
      window.removeEventListener("keydown", skip);
      window.clearTimeout(timer.current);
    };
  }, [show]);

  if (!show) return null;

  return (
    <div
      className={`splash ${loaded ? "loaded" : ""} ${leaving ? "leaving" : ""}`}
      onClick={() => setLeaving(true)}
      aria-hidden="true"
    >
      {/* Portrait screens: the GIF is letterboxed; these fill the bands above and below it
          and split open in step with the GIF's own curtains. */}
      <div className="curtain top left" />
      <div className="curtain top right" />
      <div className="curtain bottom left" />
      <div className="curtain bottom right" />
      <img
        src={SRC}
        alt=""
        draggable={false}
        onLoad={() => {
          setLoaded(true);
          timer.current = window.setTimeout(finish, PLAY_MS);
        }}
        onError={() => setLeaving(true)}
      />
    </div>
  );
}
