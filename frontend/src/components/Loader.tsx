import loader from "../assets/loader.gif";
import logo from "../assets/logo.png";

/**
 * Shown while something is being generated or loaded: the pencil draws the wizard.
 * loader.gif is 80×80 pixel art; sizes are 0.5×, 1× and 2× so pixels stay crisp.
 */
export function Loader({
  label,
  size = "md",
  inline = false,
  quick = false,
}: {
  label?: string;
  size?: "sm" | "md" | "lg";
  /** Small, on one line with the text (chat bubbles, list rows). */
  inline?: boolean;
  /** Short waits (opening a page or list): the logo's head bobs instead of the full animation. */
  quick?: boolean;
}) {
  const px = { sm: 40, md: 80, lg: 160 }[size];
  if (quick) {
    const lp = { sm: 32, md: 64, lg: 96 }[size];
    return (
      <div className={`loader quick ${inline ? "inline" : ""} loader-${size}`} role="status" aria-live="polite">
        <img src={logo} width={lp} height={lp} alt="" className="loader-img bob" draggable={false} />
        {label && <span className="loader-label">{label}</span>}
      </div>
    );
  }
  return (
    <div className={`loader ${inline ? "inline" : ""} loader-${size}`} role="status" aria-live="polite">
      <picture>
        {/* Reduced motion: the still wizard instead of the animation. */}
        <source srcSet={logo} media="(prefers-reduced-motion: reduce)" />
        <img src={loader} width={px} height={px} alt="" className="loader-img" draggable={false} />
      </picture>
      {label && <span className="loader-label">{label}</span>}
    </div>
  );
}
