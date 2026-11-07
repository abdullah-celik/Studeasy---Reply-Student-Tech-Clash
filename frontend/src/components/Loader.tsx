import pencil from "../assets/loader.gif";
import logo from "../assets/logo.png";
import rocket from "../assets/rocket.gif";

/**
 * Shown while something is being generated or loaded. Two animations:
 * - pencil (80×80): the pencil draws the wizard. For things being written: quizzes,
 *   flashcards, plans, grading.
 * - rocket (90×90): the wizard rides the pencil off like a rocket. For things being sent
 *   or fetched: chat replies, uploads, reels.
 * Sizes are 0.5×, 1× and 2× the GIF so pixels stay crisp.
 */
const ANIMS = {
  pencil: { src: pencil, native: 80 },
  rocket: { src: rocket, native: 90 },
} as const;
export function Loader({
  label,
  size = "md",
  inline = false,
  quick = false,
  anim = "pencil",
}: {
  label?: string;
  size?: "sm" | "md" | "lg";
  /** Small, on one line with the text (chat bubbles, list rows). */
  inline?: boolean;
  /** Short waits (opening a page or list): the logo's head bobs instead of the full animation. */
  quick?: boolean;
  anim?: keyof typeof ANIMS;
}) {
  const { src, native } = ANIMS[anim];
  const px = { sm: native / 2, md: native, lg: native * 2 }[size];
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
        <img src={src} width={px} height={px} alt="" className="loader-img" draggable={false} />
      </picture>
      {label && <span className="loader-label">{label}</span>}
    </div>
  );
}
