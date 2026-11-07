import pytest

from app.services.sm2 import MIN_EASE, SM2State, review


def test_first_successful_reviews_follow_1_then_6_days():
    s = review(SM2State(), 4)
    assert (s.interval, s.repetitions) == (1, 1)
    s = review(s, 4)
    assert (s.interval, s.repetitions) == (6, 2)


def test_third_review_multiplies_by_ease():
    s = SM2State(ease=2.5, interval=6, repetitions=2)
    assert review(s, 5).interval == 15


def test_lapse_resets_card():
    s = review(SM2State(ease=2.5, interval=15, repetitions=3), 1)
    assert (s.interval, s.repetitions) == (1, 0)
    assert s.ease < 2.5


def test_ease_never_drops_below_minimum():
    s = SM2State(ease=MIN_EASE)
    assert review(s, 0).ease == MIN_EASE


@pytest.mark.parametrize("q", [-1, 6])
def test_invalid_quality(q):
    with pytest.raises(ValueError):
        review(SM2State(), q)
