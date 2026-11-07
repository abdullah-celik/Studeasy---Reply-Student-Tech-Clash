import loader from "../assets/logo.png";

/**
 * Shown while something is being generated or loaded.
 * The animation lives in src/assets: swap the import above for the loading GIF
 * (and drop the `bob` class) to change it everywhere at once.
 */
export function Loader({
  label,
  size = "md",
  inline = false,
}: {
  label?: string;
  size?: "sm" | "md" | "lg";
  /** Small, on one line with the text (chat bubbles, list rows). */
  inline?: boolean;
}) {
  const px = { sm: 24, md: 64, lg: 96 }[size];
  return (
    <div className={`loader ${inline ? "inline" : ""} loader-${size}`} role="status" aria-live="polite">
      <img src={loader} width={px} height={px} alt="" className="loader-img bob" draggable={false} />
      {label && <span className="loader-label">{label}</span>}
    </div>
  );
}
