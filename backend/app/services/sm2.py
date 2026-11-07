"""SM-2 spaced repetition (the classic SuperMemo / Anki algorithm)."""

from dataclasses import dataclass

MIN_EASE = 1.3


@dataclass(frozen=True)
class SM2State:
    ease: float = 2.5
    interval: int = 0  # days until next review
    repetitions: int = 0  # consecutive successful reviews


def review(state: SM2State, quality: int) -> SM2State:
    """Return the new scheduling state after a review graded 0..5.

    quality < 3 counts as a lapse: the card restarts and comes back tomorrow.
    """
    if not 0 <= quality <= 5:
        raise ValueError("quality must be between 0 and 5")

    if quality >= 3:
        if state.repetitions == 0:
            interval = 1
        elif state.repetitions == 1:
            interval = 6
        else:
            interval = round(state.interval * state.ease)
        repetitions = state.repetitions + 1
    else:
        interval = 1
        repetitions = 0

    ease = state.ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    return SM2State(ease=max(MIN_EASE, round(ease, 4)), interval=interval, repetitions=repetitions)
