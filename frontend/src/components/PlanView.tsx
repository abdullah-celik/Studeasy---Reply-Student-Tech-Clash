import type { StudyPlan } from "../api/client";
import { PixelIcon, type IconName } from "./PixelIcon";

const KIND: Record<string, { icon: IconName; label: string }> = {
  review_flashcards: { icon: "cards", label: "Flashcards" },
  quiz: { icon: "quiz", label: "Quiz" },
  study: { icon: "book", label: "Study" },
  rest: { icon: "heart", label: "Rest" },
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
                <PixelIcon name={KIND[t.kind]?.icon ?? "star"} size={12} /> {KIND[t.kind]?.label ?? t.kind} · {t.minutes} min{t.concept ? ` · ${t.concept}` : ""}
                <div className="muted small">{t.note}</div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
