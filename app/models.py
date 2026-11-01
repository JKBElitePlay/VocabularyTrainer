"""SQLAlchemy models for vocabulary, practice sessions, and badges."""

from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VocabularyFolder(Base):
    """A named collection of vocabulary."""

    __tablename__ = "vocabulary_folders"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    vocabulary: Mapped[list["Vocabulary"]] = relationship(
        back_populates="folder", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["TrainingSession"]] = relationship(
        back_populates="folder", cascade="all, delete-orphan"
    )


class Vocabulary(Base):
    """A German-English vocabulary pair and its learning history."""

    __tablename__ = "vocabulary"

    id: Mapped[int] = mapped_column(primary_key=True)
    folder_id: Mapped[int] = mapped_column(
        ForeignKey("vocabulary_folders.id", ondelete="CASCADE"), index=True
    )
    german: Mapped[str] = mapped_column(String(250))
    english: Mapped[str] = mapped_column(String(250))
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    hint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    example_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    partial_count: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    difficulty_score: Mapped[float] = mapped_column(Float, default=0.0)
    last_practiced: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    folder: Mapped[VocabularyFolder] = relationship(back_populates="vocabulary")
    results: Mapped[list["TrainingResult"]] = relationship(cascade="all, delete-orphan")


class TrainingSession(Base):
    """A single practice run."""

    __tablename__ = "training_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), index=True
    )
    game_mode: Mapped[str] = mapped_column(String(30))
    answer_direction: Mapped[str] = mapped_column(String(5), default="de-en")
    target_questions: Mapped[int] = mapped_column(Integer, default=10)
    category_filter: Mapped[str | None] = mapped_column(Text, nullable=True)
    vocabulary_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    folder_id: Mapped[int] = mapped_column(
        ForeignKey("vocabulary_folders.id", ondelete="CASCADE")
    )
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    correct_answers: Mapped[int] = mapped_column(Integer, default=0)
    partial_answers: Mapped[int] = mapped_column(Integer, default=0)
    wrong_answers: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    results: Mapped[list["TrainingResult"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    folder: Mapped[VocabularyFolder] = relationship(back_populates="sessions")


class TrainingResult(Base):
    """An individual answer recorded during a training session."""

    __tablename__ = "training_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    vocabulary_id: Mapped[int] = mapped_column(
        ForeignKey("vocabulary.id", ondelete="CASCADE")
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("training_sessions.id", ondelete="CASCADE"), index=True
    )
    answer: Mapped[str] = mapped_column(Text, default="")
    result_type: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), index=True
    )
    session: Mapped[TrainingSession] = relationship(back_populates="results")


class Badge(Base):
    """The highest daily learning badge earned on a given date."""

    __tablename__ = "badges"
    __table_args__ = (UniqueConstraint("badge_date", name="uq_badges_badge_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    badge_date: Mapped[date] = mapped_column(Date, index=True)
    badge_type: Mapped[str] = mapped_column(String(20))
