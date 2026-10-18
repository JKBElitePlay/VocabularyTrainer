"""Request and response models for the HTTP API."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FolderCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)


class FolderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    vocabulary_count: int = 0


class VocabularyData(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    german: str = Field(min_length=1, max_length=250)
    english: str = Field(min_length=1, max_length=250)
    category: str | None = Field(default=None, max_length=120)
    hint: str | None = Field(default=None, max_length=500)
    example_sentence: str | None = Field(default=None, max_length=2000)


class VocabularyCreate(VocabularyData):
    pass


class VocabularyUpdate(VocabularyData):
    pass


class VocabularyRead(VocabularyData):
    model_config = ConfigDict(from_attributes=True)

    id: int
    folder_id: int
    correct_count: int
    partial_count: int
    wrong_count: int
    difficulty_score: float
    last_practiced: datetime | None


class TrainingCreate(BaseModel):
    folder_id: int
    game_mode: Literal["de-en", "en-de", "flashcards", "matching"]
    answer_direction: Literal["de-en", "en-de"] = "de-en"
    target_questions: Literal[10, 20, 30, 50, 75, 100] = 10
    categories: list[str] | None = None
    include_uncategorized: bool = True


class TrainingRead(BaseModel):
    id: int
    game_mode: str
    total_questions: int
    correct_answers: int
    partial_answers: int
    wrong_answers: int
    score: float


class AnswerCreate(BaseModel):
    vocabulary_id: int
    answer: str = Field(default="", max_length=1000)
    result_type: Literal["correct", "partial", "wrong"] | None = None
    help_used: bool = False


class AnswerRead(BaseModel):
    result_type: Literal["correct", "partial", "wrong"]
    expected_answer: str
    answer: str
    points: float
    message: str
    complete: bool = False
    total_questions: int
    target_questions: int


class ImportRow(VocabularyData):
    pass


class ImportRequest(BaseModel):
    rows: list[ImportRow] = Field(max_length=10000)


class BadgeRead(BaseModel):
    date: date
    badge_type: str


class DailyHistory(BaseModel):
    date: date
    answers: int


class StatisticsRead(BaseModel):
    learned_vocabulary: int
    correct_answers: int
    partial_answers: int
    wrong_answers: int
    success_rate: float
    streak_days: int
    history: list[DailyHistory]
    difficult_words: list[dict]
    favorite_words: list[dict]
    badges: list[BadgeRead]
