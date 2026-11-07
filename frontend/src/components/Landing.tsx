import { useState } from "react";
import pencil from "../assets/loader.gif";
import type { LegalDoc } from "../lib/legal";
import { LegalDialog, LegalLinks } from "./Legal";
import { PixelIcon, type IconName } from "./PixelIcon";

const FEATURES: { icon: IconName; title: string; text: string; tint: string }[] = [
  { icon: "chat", title: "A tutor that read your notes", text: "Ask anything. Answers come from your own material, with the slide or page they're based on.", tint: "sky" },
  { icon: "quiz", title: "Quizzes on demand", text: "Multiple choice, true/false or open questions, graded with feedback on what you missed.", tint: "peach" },
  { icon: "cards", title: "Flashcards that come back", text: "Spaced repetition brings each card back right before you'd forget it.", tint: "mint" },
  { icon: "reels", title: "Study reels", text: "A swipeable feed of bite-size explainers, myth vs fact and mnemonics on your weakest topics.", tint: "pink" },
  { icon: "plan", title: "A plan to your exam", text: "Add your exam date and get a day-by-day plan that starts with what you know least.", tint: "butter" },
  { icon: "folder", title: "Your material, your way", text: "PDF, slides, Word or text files. We read them and keep only the text, never the originals.", tint: "lavender" },
];

const STEPS = [
  { n: 1, title: "Create a course", text: "One per subject, like Biology or Macroeconomics." },
  { n: 2, title: "Add your material", text: "Drop in lecture slides, notes or readings." },
  { n: 3, title: "Study with the wizard", text: "Chat, quiz yourself, review cards and follow your plan." },
];

/** Public front page for visitors who aren't signed in. Draft: copy and layout to be refined. */
export function Landing({ onSignUp, onLogIn }: { onSignUp: () => void; onLogIn: () => void }) {
  const [legal, setLegal] = useState<LegalDoc | null>(null);

  return (
    <div className="landing">
      <section className="hero">
        <div className="hero-text">
          <h1>Study smarter with your own notes</h1>
          <p className="lead">
            Upload your slides and notes. Studeasy turns them into a tutor, quizzes, flashcards, study reels and a plan
            that adapts to what you still need to learn.
          </p>
          <div className="row wrap hero-cta">
            <button className="big" onClick={onSignUp}>Get started</button>
            <button className="secondary big" onClick={onLogIn}>I already have an account</button>
          </div>
          <p className="muted small">Works in your browser and installs on your phone.</p>
        </div>
        <div className="hero-art" aria-hidden="true">
          <img src={pencil} width={240} height={240} alt="" className="loader-img" draggable={false} />
        </div>
      </section>

      <section className="features" aria-label="Features">
        {FEATURES.map((f) => (
          <div key={f.title} className={`feature tint-${f.tint}`}>
            <PixelIcon name={f.icon} size={24} />
            <h3>{f.title}</h3>
            <p>{f.text}</p>
          </div>
        ))}
      </section>

      <section className="steps" aria-label="How it works">
        <h2>How it works</h2>
        <ol>
          {STEPS.map((s) => (
            <li key={s.n}>
              <span className="step-n">{s.n}</span>
              <div>
                <strong>{s.title}</strong>
                <p className="muted">{s.text}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="final-cta">
        <h2>Ready when you are</h2>
        <button className="big" onClick={onSignUp}>Get started</button>
      </section>

      <footer className="landing-foot muted small">
        <span>© {new Date().getFullYear()} Studeasy</span>
        <LegalLinks open={setLegal} />
      </footer>
      <LegalDialog doc={legal} onClose={() => setLegal(null)} />
    </div>
  );
}
