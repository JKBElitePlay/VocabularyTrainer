"""FastAPI application and HTTP endpoints."""

import csv
import io
import json
import random
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import false, func, inspect, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base, create_database, get_db
from app.models import Badge, TrainingResult, TrainingSession, Vocabulary, VocabularyFolder
from app.schemas import (
    AnswerCreate,
    AnswerRead,
    FolderCreate,
    ImportRequest,
    TrainingCreate,
    VocabularyCreate,
    VocabularyRead,
    VocabularyUpdate,
)
from app.services import badge_for, evaluate_answer, points_for, update_difficulty

BADGE_THRESHOLDS = {"bronze": 10, "silver": 30, "gold": 50, "diamond": 100}
STATIC_DIR = Path(__file__).parent / "static"


def create_app(database_url: str | None = None) -> FastAPI:
    """Build the application, optionally using a test-specific SQLite URL."""
    application = FastAPI(title="Vokabeltrainer", version="0.1.0")
    engine, session_factory = create_database(database_url)
    Base.metadata.create_all(engine)
    training_columns = {
        column["name"] for column in inspect(engine).get_columns("training_sessions")
    }
    with engine.begin() as connection:
        if "target_questions" not in training_columns:
            connection.execute(
                text(
                    "ALTER TABLE training_sessions "
                    "ADD COLUMN target_questions INTEGER NOT NULL DEFAULT 10"
                )
            )
        if "answer_direction" not in training_columns:
            connection.execute(
                text(
                    "ALTER TABLE training_sessions "
                    "ADD COLUMN answer_direction VARCHAR(5) NOT NULL DEFAULT 'de-en'"
                )
            )
        if "category_filter" not in training_columns:
            connection.execute(
                text(
                    "ALTER TABLE training_sessions "
                    "ADD COLUMN category_filter TEXT"
                )
            )
    application.state.engine = engine
    application.state.session_factory = session_factory

    @application.get("/api/folders")
    def list_folders(db: Session = Depends(get_db)):
        folders = db.execute(
            select(VocabularyFolder, func.count(Vocabulary.id))
            .outerjoin(Vocabulary)
            .group_by(VocabularyFolder.id)
            .order_by(VocabularyFolder.name)
        ).all()
        return [
            {
                "id": folder.id,
                "name": folder.name,
                "created_at": folder.created_at,
                "vocabulary_count": vocabulary_count,
            }
            for folder, vocabulary_count in folders
        ]

    @application.post("/api/folders", status_code=201)
    def create_folder(payload: FolderCreate, db: Session = Depends(get_db)):
        folder = VocabularyFolder(name=payload.name.strip())
        if not folder.name:
            raise HTTPException(422, "Der Mappenname darf nicht leer sein.")
        db.add(folder)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(409, "Eine Mappe mit diesem Namen existiert bereits.") from exc
        db.refresh(folder)
        return {"id": folder.id, "name": folder.name, "vocabulary_count": 0}

    @application.patch("/api/folders/{folder_id}")
    def rename_folder(folder_id: int, payload: FolderCreate, db: Session = Depends(get_db)):
        folder = db.get(VocabularyFolder, folder_id)
        if folder is None:
            raise HTTPException(404, "Mappe nicht gefunden.")
        folder.name = payload.name.strip()
        if not folder.name:
            raise HTTPException(422, "Der Mappenname darf nicht leer sein.")
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(409, "Eine Mappe mit diesem Namen existiert bereits.") from exc
        return {"id": folder.id, "name": folder.name, "vocabulary_count": len(folder.vocabulary)}

    @application.delete("/api/folders/{folder_id}", status_code=204)
    def delete_folder(folder_id: int, db: Session = Depends(get_db)):
        folder = db.get(VocabularyFolder, folder_id)
        if folder is None:
            raise HTTPException(404, "Mappe nicht gefunden.")
        db.delete(folder)
        db.commit()
        return Response(status_code=204)

    @application.get("/api/folders/{folder_id}/vocabulary", response_model=list[VocabularyRead])
    def list_vocabulary(folder_id: int, db: Session = Depends(get_db)):
        if db.get(VocabularyFolder, folder_id) is None:
            raise HTTPException(404, "Mappe nicht gefunden.")
        return db.scalars(
            select(Vocabulary).where(Vocabulary.folder_id == folder_id).order_by(Vocabulary.german)
        ).all()

    @application.get("/api/folders/{folder_id}/categories")
    def list_categories(folder_id: int, db: Session = Depends(get_db)):
        if db.get(VocabularyFolder, folder_id) is None:
            raise HTTPException(404, "Mappe nicht gefunden.")
        counts = db.execute(
            select(Vocabulary.category, func.count(Vocabulary.id))
            .where(Vocabulary.folder_id == folder_id)
            .group_by(Vocabulary.category)
            .order_by(Vocabulary.category)
        ).all()
        return {
            "categories": [
                {"name": name, "count": count}
                for name, count in counts
                if name is not None
            ],
            "uncategorized_count": sum(count for name, count in counts if name is None),
            "total_count": sum(count for _, count in counts),
        }

    @application.post(
        "/api/folders/{folder_id}/vocabulary", response_model=VocabularyRead, status_code=201
    )
    def create_vocabulary(
        folder_id: int, payload: VocabularyCreate, db: Session = Depends(get_db)
    ):
        if db.get(VocabularyFolder, folder_id) is None:
            raise HTTPException(404, "Mappe nicht gefunden.")
        word = Vocabulary(folder_id=folder_id, **payload.model_dump())
        db.add(word)
        db.commit()
        db.refresh(word)
        return word

    @application.put(
        "/api/vocabulary/{vocabulary_id}", response_model=VocabularyRead
    )
    def edit_vocabulary(
        vocabulary_id: int, payload: VocabularyUpdate, db: Session = Depends(get_db)
    ):
        word = db.get(Vocabulary, vocabulary_id)
        if word is None:
            raise HTTPException(404, "Vokabel nicht gefunden.")
        for key, value in payload.model_dump().items():
            setattr(word, key, value)
        db.commit()
        return word

    @application.delete("/api/vocabulary/{vocabulary_id}", status_code=204)
    def delete_vocabulary(vocabulary_id: int, db: Session = Depends(get_db)):
        word = db.get(Vocabulary, vocabulary_id)
        if word is None:
            raise HTTPException(404, "Vokabel nicht gefunden.")
        db.delete(word)
        db.commit()
        return Response(status_code=204)

    @application.post("/api/folders/{folder_id}/import/preview")
    async def preview_import(folder_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
        if db.get(VocabularyFolder, folder_id) is None:
            raise HTTPException(404, "Mappe nicht gefunden.")
        contents = await file.read(5_000_001)
        if len(contents) > 5_000_000:
            raise HTTPException(413, "Die CSV-Datei darf höchstens 5 MB groß sein.")
        try:
            text = contents.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(400, "Die Datei muss UTF-8-kodiert sein.") from exc
        reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=";")
        if not reader.fieldnames:
            raise HTTPException(400, "Die CSV-Datei enthält keine Kopfzeile.")
        headers = {header.strip().casefold(): header for header in reader.fieldnames if header}
        german_key = headers.get("deutsch") or headers.get("german")
        english_key = headers.get("englisch") or headers.get("english")
        if not german_key or not english_key:
            raise HTTPException(400, "Erforderliche Spalten: deutsch, englisch.")

        existing = db.scalars(select(Vocabulary).where(Vocabulary.folder_id == folder_id)).all()
        seen = {(word.german.casefold(), word.english.casefold()) for word in existing}
        category_key = headers.get("kategorie") or headers.get("category") or ""
        hint_key = headers.get("hinweis") or headers.get("hint") or ""
        example_key = (
            headers.get("beispielsatz")
            or headers.get("example_sentence")
            or headers.get("examplesentence")
            or ""
        )
        rows, errors, duplicates = [], [], 0
        for line_number, row in enumerate(reader, start=2):
            german = (row.get(german_key) or "").strip()
            english = (row.get(english_key) or "").strip()
            if not german or not english:
                errors.append({"line": line_number, "message": "Deutsch und Englisch sind erforderlich."})
                continue
            category = (row.get(category_key) or "").strip()
            hint = (row.get(hint_key) or "").strip()
            example_sentence = (row.get(example_key) or "").strip()
            if len(german) > 250 or len(english) > 250:
                errors.append({"line": line_number, "message": "Wörter dürfen höchstens 250 Zeichen lang sein."})
                continue
            if len(category) > 120 or len(hint) > 500 or len(example_sentence) > 2000:
                errors.append({"line": line_number, "message": "Ein optionales Feld überschreitet die erlaubte Länge."})
                continue
            identity = (german.casefold(), english.casefold())
            if identity in seen:
                duplicates += 1
                continue
            seen.add(identity)
            rows.append(
                {
                    "german": german,
                    "english": english,
                    "category": category or None,
                    "hint": hint or None,
                    "example_sentence": example_sentence or None,
                }
            )
            if len(rows) + duplicates + len(errors) > 10000:
                raise HTTPException(413, "Es können höchstens 10.000 CSV-Zeilen importiert werden.")
        return {
            "found": len(rows) + duplicates + len(errors),
            "valid": len(rows),
            "duplicates": duplicates,
            "errors": errors,
            "rows": rows,
        }

    @application.post("/api/folders/{folder_id}/import")
    def import_vocabulary(
        folder_id: int, payload: ImportRequest, db: Session = Depends(get_db)
    ):
        if db.get(VocabularyFolder, folder_id) is None:
            raise HTTPException(404, "Mappe nicht gefunden.")
        existing = db.scalars(select(Vocabulary).where(Vocabulary.folder_id == folder_id)).all()
        seen = {(word.german.casefold(), word.english.casefold()) for word in existing}
        imported = 0
        for row in payload.rows:
            identity = (row.german.strip().casefold(), row.english.strip().casefold())
            if identity in seen:
                continue
            seen.add(identity)
            db.add(Vocabulary(folder_id=folder_id, **row.model_dump()))
            imported += 1
        db.commit()
        return {"found": len(payload.rows), "imported": imported, "duplicates": len(payload.rows) - imported}

    @application.get("/api/folders/{folder_id}/export")
    def export_vocabulary(folder_id: int, db: Session = Depends(get_db)):
        if db.get(VocabularyFolder, folder_id) is None:
            raise HTTPException(404, "Mappe nicht gefunden.")
        words = db.scalars(
            select(Vocabulary).where(Vocabulary.folder_id == folder_id).order_by(Vocabulary.german)
        ).all()
        output = io.StringIO(newline="")
        writer = csv.writer(output, delimiter=";")
        writer.writerow(["deutsch", "englisch", "kategorie", "hinweis", "beispielsatz"])
        writer.writerows(
            [w.german, w.english, w.category or "", w.hint or "", w.example_sentence or ""]
            for w in words
        )
        return Response(
            content="\ufeff" + output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="vokabelmappe-{folder_id}.csv"'},
        )

    @application.post("/api/training", status_code=201)
    def create_training(payload: TrainingCreate, db: Session = Depends(get_db)):
        folder = db.get(VocabularyFolder, payload.folder_id)
        if folder is None:
            raise HTTPException(404, "Mappe nicht gefunden.")
        if payload.categories is not None:
            category_filter = {
                "categories": sorted(set(payload.categories)),
                "include_uncategorized": payload.include_uncategorized,
            }
        else:
            category_filter = None
        training_query = select(Vocabulary).where(Vocabulary.folder_id == payload.folder_id)
        training_query = apply_category_filter(training_query, category_filter)
        if not db.scalar(select(func.count()).select_from(training_query.subquery())):
            raise HTTPException(400, "Diese Mappe enthält noch keine Vokabeln.")
        session = TrainingSession(
            folder_id=payload.folder_id,
            game_mode=payload.game_mode,
            answer_direction=(
                payload.answer_direction
                if payload.game_mode == "flashcards"
                else ("en-de" if payload.game_mode == "en-de" else "de-en")
            ),
            target_questions=payload.target_questions,
            category_filter=(
                json.dumps(category_filter, ensure_ascii=False)
                if category_filter is not None
                else None
            ),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return {
            "id": session.id,
            "folder_id": session.folder_id,
            "game_mode": session.game_mode,
            "answer_direction": session.answer_direction,
            "target_questions": session.target_questions,
            "category_filter": category_filter,
            "total_questions": session.total_questions,
        }

    @application.get("/api/training/{session_id}/question")
    def next_question(session_id: int, db: Session = Depends(get_db)):
        session = db.get(TrainingSession, session_id)
        if session is None:
            raise HTTPException(404, "Lernsitzung nicht gefunden.")
        if session.total_questions >= session.target_questions:
            return {"complete": True}
        selected = select_training_vocabulary(session, db)
        if selected is None:
            raise HTTPException(400, "Diese Mappe enthält keine Vokabeln mehr.")
        translation = (
            session.answer_direction
            if session.game_mode == "flashcards"
            else ("en-de" if session.game_mode == "en-de" else "de-en")
        )
        prompt = selected.german if translation == "de-en" else selected.english
        expected = selected.english if translation == "de-en" else selected.german
        return {
            "complete": False,
            "vocabulary_id": selected.id,
            "prompt": prompt,
            "translation": translation,
            "hint": selected.hint,
            "example_sentence": selected.example_sentence,
            "first_letter": expected[0],
            "word_length": len(expected),
            "partial_hint": partial_hint(expected),
            "questions_remaining": session.target_questions - session.total_questions,
        }

    @application.get("/api/training/{session_id}/matching")
    def matching_round(session_id: int, db: Session = Depends(get_db)):
        session = db.get(TrainingSession, session_id)
        if session is None:
            raise HTTPException(404, "Lernsitzung nicht gefunden.")
        if session.game_mode != "matching":
            raise HTTPException(400, "Diese Lernsitzung verwendet kein Zuordnungsspiel.")
        if session.total_questions >= session.target_questions:
            return {"complete": True, "left": [], "right": []}
        chosen = []
        for _ in range(min(5, session.target_questions - session.total_questions)):
            word = select_training_vocabulary(session, db, exclude_ids={item.id for item in chosen})
            if word is None:
                break
            chosen.append(word)
        left = [{"id": word.id, "text": word.german} for word in chosen]
        right = [{"id": word.id, "text": word.english} for word in chosen]
        random.shuffle(left)
        random.shuffle(right)
        return {"complete": False, "left": left, "right": right}

    @application.get("/api/training/{session_id}/solution/{vocabulary_id}")
    def flashcard_solution(
        session_id: int, vocabulary_id: int, db: Session = Depends(get_db)
    ):
        session = db.get(TrainingSession, session_id)
        word = db.get(Vocabulary, vocabulary_id)
        if session is None or word is None or word.folder_id != session.folder_id:
            raise HTTPException(404, "Karteikarte nicht gefunden.")
        if db.scalar(
            training_vocabulary_query(session).where(Vocabulary.id == word.id)
        ) is None:
            raise HTTPException(404, "Vokabel gehört nicht zu dieser Lernsitzung.")
        if session.game_mode != "flashcards":
            raise HTTPException(400, "Diese Lernsitzung verwendet keine Karteikarten.")
        answer = word.english if session.answer_direction == "de-en" else word.german
        return {"answer": answer, "direction": session.answer_direction}

    @application.post(
        "/api/training/{session_id}/answers", response_model=AnswerRead
    )
    def submit_answer(session_id: int, payload: AnswerCreate, db: Session = Depends(get_db)):
        session = db.get(TrainingSession, session_id)
        word = db.get(Vocabulary, payload.vocabulary_id)
        if session is None:
            raise HTTPException(404, "Lernsitzung nicht gefunden.")
        if word is None or word.folder_id != session.folder_id:
            raise HTTPException(404, "Vokabel gehört nicht zu dieser Lernsitzung.")
        if db.scalar(
            training_vocabulary_query(session).where(Vocabulary.id == word.id)
        ) is None:
            raise HTTPException(404, "Vokabel gehört nicht zu dieser Lernsitzung.")

        if session.total_questions >= session.target_questions:
            raise HTTPException(409, "Die gewählte Anzahl an Fragen wurde bereits erreicht.")
        if session.game_mode == "matching" and payload.result_type is None:
            raise HTTPException(422, "Bitte übermittle das Ergebnis der Zuordnung.")
        target_is_english = (
            session.answer_direction == "de-en"
            if session.game_mode == "flashcards"
            else session.game_mode == "de-en"
        )
        expected = word.english if target_is_english else word.german
        result_type = payload.result_type or evaluate_answer(payload.answer, expected)
        if session.game_mode in {"de-en", "en-de"}:
            result_type = evaluate_answer(payload.answer, expected)
        elif payload.result_type is None:
            raise HTTPException(422, "Dieser Spielmodus benötigt eine Bewertung.")
        points = points_for(result_type, payload.help_used)
        setattr(word, f"{result_type}_count", getattr(word, f"{result_type}_count") + 1)
        word.last_practiced = datetime.now(UTC)
        update_difficulty(word)
        session.total_questions += 1
        if result_type == "correct":
            session.correct_answers += 1
        elif result_type == "partial":
            session.partial_answers += 1
        else:
            session.wrong_answers += 1
        session.score += points
        db.add(TrainingResult(
            vocabulary_id=word.id,
            session_id=session.id,
            answer=payload.answer,
            result_type=result_type,
        ))
        db.flush()

        if result_type == "correct":
            today = date.today()
            daily_correct = db.scalar(
                select(func.count(TrainingResult.id))
                .join(TrainingSession)
                .where(
                    func.date(TrainingResult.created_at) == today.isoformat(),
                    TrainingResult.result_type == "correct",
                )
            )
            tier = badge_for(daily_correct or 0)
            if tier:
                badge = db.scalar(select(Badge).where(Badge.badge_date == today))
                if badge is None:
                    db.add(Badge(badge_date=today, badge_type=tier))
                elif BADGE_THRESHOLDS[tier] > BADGE_THRESHOLDS[badge.badge_type]:
                    badge.badge_type = tier
        db.commit()
        messages = {"correct": "Richtig!", "partial": "Fast richtig!", "wrong": "Leider falsch."}
        return AnswerRead(
            result_type=result_type,
            expected_answer=expected,
            answer=payload.answer,
            points=points,
            message=messages[result_type],
            complete=session.total_questions >= session.target_questions,
            total_questions=session.total_questions,
            target_questions=session.target_questions,
        )

    @application.get("/api/training/{session_id}")
    def training_summary(session_id: int, db: Session = Depends(get_db)):
        session = db.get(TrainingSession, session_id)
        if session is None:
            raise HTTPException(404, "Lernsitzung nicht gefunden.")
        return {
            "id": session.id,
            "game_mode": session.game_mode,
            "total_questions": session.total_questions,
            "correct_answers": session.correct_answers,
            "partial_answers": session.partial_answers,
            "wrong_answers": session.wrong_answers,
            "score": session.score,
            "target_questions": session.target_questions,
            "answer_direction": session.answer_direction,
        }

    @application.get("/api/statistics")
    def statistics(db: Session = Depends(get_db)):
        words = db.scalars(select(Vocabulary)).all()
        correct = sum(word.correct_count for word in words)
        partial = sum(word.partial_count for word in words)
        wrong = sum(word.wrong_count for word in words)
        total = correct + partial + wrong
        results = db.execute(
            select(func.date(TrainingResult.created_at), func.count(TrainingResult.id))
            .group_by(func.date(TrainingResult.created_at))
        ).all()
        daily = {date.fromisoformat(day): count for day, count in results}
        cursor = date.today() if date.today() in daily else date.today() - timedelta(days=1)
        streak = 0
        while cursor in daily:
            streak += 1
            cursor -= timedelta(days=1)
        history_start = date.today() - timedelta(days=29)
        history = [
            {"date": day.isoformat(), "answers": daily[day]}
            for day in sorted(daily)
            if day >= history_start
        ]
        difficult = sorted(
            (
                {
                    "id": w.id,
                    "german": w.german,
                    "english": w.english,
                    "wrong_count": w.wrong_count,
                    "error_rate": round(w.wrong_count / (w.correct_count + w.partial_count + w.wrong_count), 3),
                }
                for w in words
                if w.wrong_count + w.correct_count + w.partial_count
            ),
            key=lambda item: (item["error_rate"], item["wrong_count"]),
            reverse=True,
        )[:20]
        favorites = sorted(
            (
                {"id": w.id, "german": w.german, "english": w.english, "correct_count": w.correct_count}
                for w in words
                if w.correct_count
            ),
            key=lambda item: item["correct_count"],
            reverse=True,
        )[:20]
        return {
            "learned_vocabulary": sum(bool(w.correct_count + w.partial_count + w.wrong_count) for w in words),
            "correct_answers": correct,
            "partial_answers": partial,
            "wrong_answers": wrong,
            "success_rate": round((correct + partial * 0.5) / total * 100, 1) if total else 0.0,
            "streak_days": streak,
            "history": history,
            "difficult_words": difficult,
            "favorite_words": favorites,
            "badges": [
                {"date": badge.badge_date.isoformat(), "badge_type": badge.badge_type}
                for badge in db.scalars(select(Badge).order_by(Badge.badge_date.desc())).all()
            ],
        }

    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @application.get("/", include_in_schema=False)
    def home():
        return Response(
            content=(STATIC_DIR / "index.html").read_text(encoding="utf-8"),
            media_type="text/html",
        )

    return application


def partial_hint(answer: str) -> str:
    """Reveal a random portion of a word while masking its remaining letters."""
    reveal_count = max(1, round(len(answer) * 0.4))
    revealed = set(random.sample(range(len(answer)), min(reveal_count, len(answer))))
    return " ".join(character if index in revealed else "_" for index, character in enumerate(answer))


def select_training_vocabulary(
    session: TrainingSession,
    db: Session,
    exclude_ids: set[int] | None = None,
) -> Vocabulary | None:
    """Select unasked words first, then latest misses, then latest correct answers."""
    words = db.scalars(training_vocabulary_query(session)).all()
    if exclude_ids:
        words = [word for word in words if word.id not in exclude_ids]
    if not words:
        return None

    results = db.scalars(
        select(TrainingResult)
        .where(TrainingResult.session_id == session.id)
        .order_by(TrainingResult.created_at.desc(), TrainingResult.id.desc())
    ).all()
    latest_result = {}
    for result in results:
        latest_result.setdefault(result.vocabulary_id, result.result_type)

    priority = {"wrong": 0, "partial": 1, "correct": 2}
    highest_priority = min(
        (priority[latest_result[word.id]] if word.id in latest_result else -1)
        for word in words
    )
    candidates = [
        word
        for word in words
        if (priority[latest_result[word.id]] if word.id in latest_result else -1)
        == highest_priority
    ]
    weights = [max(0.1, word.difficulty_score + 1) for word in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]


def training_vocabulary_query(session: TrainingSession):
    """Build the vocabulary query restricted to the session's selected categories."""
    query = select(Vocabulary).where(Vocabulary.folder_id == session.folder_id)
    category_filter = (
        json.loads(session.category_filter) if session.category_filter is not None else None
    )
    return apply_category_filter(query, category_filter)


def apply_category_filter(query, category_filter: dict | None):
    """Add a category selection to a vocabulary query when one was submitted."""
    if category_filter is None:
        return query
    conditions = []
    if category_filter["categories"]:
        conditions.append(Vocabulary.category.in_(category_filter["categories"]))
    if category_filter["include_uncategorized"]:
        conditions.append(Vocabulary.category.is_(None))
    return query.where(or_(*conditions)) if conditions else query.where(false())


app = create_app()
