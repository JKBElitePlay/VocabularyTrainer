from app.services import badge_for, evaluate_answer, points_for


def test_answer_evaluation_normalizes_case_and_whitespace():
    assert evaluate_answer("  HOUSE  ", "house") == "correct"


def test_answer_evaluation_detects_a_small_typo():
    assert evaluate_answer("hous", "house") == "partial"
    assert evaluate_answer("horse", "house") == "wrong"


def test_help_reduces_the_available_points_by_one_quarter():
    assert points_for("correct", help_used=True) == 0.75
    assert points_for("partial", help_used=True) == 0.375


def test_badges_award_only_the_highest_earned_tier():
    assert badge_for(9) is None
    assert badge_for(10) == "bronze"
    assert badge_for(30) == "silver"
    assert badge_for(58) == "gold"
    assert badge_for(100) == "diamond"
