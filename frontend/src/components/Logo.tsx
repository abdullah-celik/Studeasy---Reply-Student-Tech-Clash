import logo from "../assets/logo.png";

/** The Studeasy wizard. 32×32 pixel art: keep sizes at multiples of 32 so pixels stay crisp. */
export function Logo({ size = 32, className = "" }: { size?: 32 | 64 | 96 | 128; className?: string }) {
  return <img src={logo} width={size} height={size} alt="Studeasy" className={`logo-img ${className}`} draggable={false} />;
}
