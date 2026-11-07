import type { Reel } from "../api/client";

export const TYPE_LABEL: Record<Reel["type"], string> = {
  explainer: "Explainer",
  quiz: "Quick quiz",
  flashcard: "Flashcard",
  myth_fact: "Myth vs fact",
  mnemonic: "Mnemonic",
  break: "Break time",
};

export const reelId = (r: Reel) => ("id" in r ? r.id : null);
