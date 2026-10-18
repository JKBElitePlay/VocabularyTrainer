"""Learning, answer evaluation, and badge rules."""

from difflib import SequenceMatcher

from app.models import Vocabulary


def normalize_answer(value: str) -> str:
    """Normalize harmless differences in whitespace and letter case."""
    return " ".join(value.casefold().split())


def evaluate_answer(answer: str, expected: str) -> str:
    """Classify an answer as correct, a close typo, or wrong."""
    normalized_answer = normalize_answer(answer)
    normalized_expected = normalize_answer(expected)
    if normalized_answer == normalized_expected:
        return "correct"
    if normalized_answer and SequenceMatcher(
        None, normalized_answer, normalized_expected
    ).ratio() > 0.8:
        return "partial"
    return "wrong"


def update_difficulty(vocabulary: Vocabulary) -> None:
    """Recalculate a word's score from its accumulated answer counts."""
    vocabulary.difficulty_score = (
        vocabulary.wrong_count * 2 - vocabulary.correct_count * 0.5
    )


def points_for(result_type: str, help_used: bool = False) -> float:
    """Return the score awarded for an answer, including any help penalty."""
    points = {"correct": 1.0, "partial": 0.5, "wrong": 0.0}[result_type]
    return points * (0.75 if help_used else 1.0)


def badge_for(correct_answers: int) -> str | None:
    """Return the highest badge tier earned for the day's correct answers."""
    tiers = ((100, "diamond"), (50, "gold"), (30, "silver"), (10, "bronze"))
    return next((badge for threshold, badge in tiers if correct_answers >= threshold), None)
