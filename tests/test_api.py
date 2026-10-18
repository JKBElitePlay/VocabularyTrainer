import io
import sqlite3

from fastapi.testclient import TestClient

from app.main import create_app


def make_client(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'test.db'}")
    return TestClient(app)


def test_vocabulary_practice_and_statistics_are_persisted(tmp_path):
    with make_client(tmp_path) as client:
        folder = client.post("/api/folders", json={"name": "Tiere"}).json()
        word = client.post(
            f"/api/folders/{folder['id']}/vocabulary",
            json={"german": "Haus", "english": "house"},
        ).json()

        training = client.post(
            "/api/training", json={"folder_id": folder["id"], "game_mode": "de-en"}
        ).json()
        question = client.get(f"/api/training/{training['id']}/question").json()
        assert question["prompt"] == "Haus"
        result = client.post(
            f"/api/training/{training['id']}/answers",
            json={"vocabulary_id": word["id"], "answer": "hous", "help_used": True},
        ).json()
        assert result["result_type"] == "partial"
        assert result["points"] == 0.375
        assert result["expected_answer"] == "house"

        stats = client.get("/api/statistics").json()
        assert stats["learned_vocabulary"] == 1
        assert stats["partial_answers"] == 1
        assert stats["success_rate"] == 50.0
        assert client.get(f"/api/training/{training['id']}").json()["total_questions"] == 1


def test_typed_answer_cannot_be_marked_correct_by_the_client(tmp_path):
    with make_client(tmp_path) as client:
        folder = client.post("/api/folders", json={"name": "Antworten"}).json()
        word = client.post(
            f"/api/folders/{folder['id']}/vocabulary",
            json={"german": "Haus", "english": "house"},
        ).json()
        training = client.post(
            "/api/training", json={"folder_id": folder["id"], "game_mode": "de-en"}
        ).json()

        result = client.post(
            f"/api/training/{training['id']}/answers",
            json={
                "vocabulary_id": word["id"],
                "answer": "wrong",
                "result_type": "correct",
            },
        ).json()
        assert result["result_type"] == "wrong"
        assert result["points"] == 0


def test_flashcards_require_a_known_or_unknown_rating(tmp_path):
    with make_client(tmp_path) as client:
        folder = client.post("/api/folders", json={"name": "Karten"}).json()
        word = client.post(
            f"/api/folders/{folder['id']}/vocabulary",
            json={"german": "Haus", "english": "house"},
        ).json()
        training = client.post(
            "/api/training",
            json={
                "folder_id": folder["id"],
                "game_mode": "flashcards",
                "answer_direction": "en-de",
            },
        ).json()
        result = client.post(
            f"/api/training/{training['id']}/answers",
            json={"vocabulary_id": word["id"], "result_type": "correct"},
        ).json()
        assert result["expected_answer"] == "Haus"
        assert client.post(
            f"/api/training/{training['id']}/answers",
            json={"vocabulary_id": word["id"], "answer": ""},
        ).status_code == 422


def test_training_shows_every_unasked_word_before_repeating_a_correct_one(tmp_path):
    with make_client(tmp_path) as client:
        folder = client.post("/api/folders", json={"name": "Erste Runde"}).json()
        words = [
            client.post(
                f"/api/folders/{folder['id']}/vocabulary",
                json={"german": german, "english": english},
            ).json()
            for german, english in [("Haus", "house"), ("Hund", "dog"), ("Katze", "cat")]
        ]
        session = client.post(
            "/api/training",
            json={"folder_id": folder["id"], "game_mode": "de-en", "target_questions": 10},
        ).json()

        first = client.get(f"/api/training/{session['id']}/question").json()
        first_result = client.post(
            f"/api/training/{session['id']}/answers",
            json={"vocabulary_id": first["vocabulary_id"], "answer": "wrong"},
        ).json()
        assert first_result["result_type"] == "wrong"
        seen = {first["vocabulary_id"]}

        for expected_result in ("correct", "correct"):
            question = client.get(f"/api/training/{session['id']}/question").json()
            assert question["vocabulary_id"] not in seen
            seen.add(question["vocabulary_id"])
            word = next(item for item in words if item["id"] == question["vocabulary_id"])
            result = client.post(
                f"/api/training/{session['id']}/answers",
                json={"vocabulary_id": word["id"], "answer": word["english"]},
            ).json()
            assert result["result_type"] == expected_result

        retry = client.get(f"/api/training/{session['id']}/question").json()
        assert retry["vocabulary_id"] == first["vocabulary_id"]
        assert retry["questions_remaining"] == 7

        for _ in range(7):
            question = client.get(f"/api/training/{session['id']}/question").json()
            word = next(item for item in words if item["id"] == question["vocabulary_id"])
            result = client.post(
                f"/api/training/{session['id']}/answers",
                json={"vocabulary_id": word["id"], "answer": word["english"]},
            ).json()

        assert result["complete"] is True
        assert result["total_questions"] == 10
        assert client.get(f"/api/training/{session['id']}/question").json()["complete"] is True
        assert client.post(
            f"/api/training/{session['id']}/answers",
            json={"vocabulary_id": words[0]["id"], "answer": "house"},
        ).status_code == 409
        assert client.get(f"/api/training/{session['id']}").json()["target_questions"] == 10


def test_flashcard_direction_and_question_count_are_saved_per_session(tmp_path):
    with make_client(tmp_path) as client:
        folder = client.post("/api/folders", json={"name": "Richtung"}).json()
        word = client.post(
            f"/api/folders/{folder['id']}/vocabulary",
            json={"german": "Haus", "english": "house"},
        ).json()

        for direction, prompt, answer in (
            ("de-en", "Haus", "house"),
            ("en-de", "house", "Haus"),
        ):
            session = client.post(
                "/api/training",
                json={
                    "folder_id": folder["id"],
                    "game_mode": "flashcards",
                    "answer_direction": direction,
                    "target_questions": 20,
                },
            ).json()
            question = client.get(f"/api/training/{session['id']}/question").json()
            assert question["prompt"] == prompt
            assert question["translation"] == direction
            solution = client.get(
                f"/api/training/{session['id']}/solution/{word['id']}"
            ).json()
            assert solution["answer"] == answer
            assert solution["direction"] == direction
            result = client.post(
                f"/api/training/{session['id']}/answers",
                json={"vocabulary_id": word["id"], "result_type": "correct"},
            ).json()
            assert result["expected_answer"] == answer
            summary = client.get(f"/api/training/{session['id']}").json()
            assert summary["answer_direction"] == direction
            assert summary["target_questions"] == 20

        assert client.post(
            "/api/training",
            json={
                "folder_id": folder["id"],
                "game_mode": "de-en",
                "target_questions": 15,
            },
        ).status_code == 422


def test_existing_training_table_is_migrated_for_new_session_options(tmp_path):
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE training_sessions (
                id INTEGER NOT NULL PRIMARY KEY,
                started_at DATETIME NOT NULL,
                game_mode VARCHAR(30) NOT NULL,
                folder_id INTEGER NOT NULL,
                total_questions INTEGER NOT NULL,
                correct_answers INTEGER NOT NULL,
                partial_answers INTEGER NOT NULL,
                wrong_answers INTEGER NOT NULL,
                score FLOAT NOT NULL
            )
            """
        )

    with TestClient(create_app(f"sqlite:///{database_path}")) as client:
        folder = client.post("/api/folders", json={"name": "Altbestand"}).json()
        client.post(
            f"/api/folders/{folder['id']}/vocabulary",
            json={"german": "Haus", "english": "house"},
        )
        session = client.post(
            "/api/training",
            json={"folder_id": folder["id"], "game_mode": "de-en", "target_questions": 30},
        )
        assert session.status_code == 201
        assert session.json()["target_questions"] == 30
        assert session.json()["answer_direction"] == "de-en"


def test_category_list_counts_words_including_uncategorized(tmp_path):
    with make_client(tmp_path) as client:
        folder = client.post("/api/folders", json={"name": "Kategorien"}).json()
        for german, english, category in (
            ("Hund", "dog", "Tiere"),
            ("Katze", "cat", "Tiere"),
            ("Brot", "bread", "Essen"),
            ("Wasser", "water", None),
        ):
            client.post(
                f"/api/folders/{folder['id']}/vocabulary",
                json={"german": german, "english": english, "category": category},
            )

        result = client.get(f"/api/folders/{folder['id']}/categories").json()
        assert result["categories"] == [
            {"name": "Essen", "count": 1},
            {"name": "Tiere", "count": 2},
        ]
        assert result["uncategorized_count"] == 1
        assert result["total_count"] == 4


def test_training_only_selects_and_accepts_vocabulary_from_selected_categories(tmp_path):
    with make_client(tmp_path) as client:
        folder = client.post("/api/folders", json={"name": "Kategorien lernen"}).json()
        selected_words = [
            client.post(
                f"/api/folders/{folder['id']}/vocabulary",
                json={"german": german, "english": english, "category": "Tiere"},
            ).json()
            for german, english in (("Hund", "dog"), ("Katze", "cat"))
        ]
        outside_word = client.post(
            f"/api/folders/{folder['id']}/vocabulary",
            json={"german": "Brot", "english": "bread", "category": "Essen"},
        ).json()
        uncategorized = client.post(
            f"/api/folders/{folder['id']}/vocabulary",
            json={"german": "Haus", "english": "house"},
        ).json()

        training = client.post(
            "/api/training",
            json={
                "folder_id": folder["id"],
                "game_mode": "de-en",
                "categories": ["Tiere"],
                "include_uncategorized": False,
            },
        ).json()
        assert training["category_filter"] == {
            "categories": ["Tiere"],
            "include_uncategorized": False,
        }

        seen = set()
        for _ in range(2):
            question = client.get(f"/api/training/{training['id']}/question").json()
            assert question["vocabulary_id"] in {word["id"] for word in selected_words}
            seen.add(question["vocabulary_id"])
            word = next(item for item in selected_words if item["id"] == question["vocabulary_id"])
            client.post(
                f"/api/training/{training['id']}/answers",
                json={"vocabulary_id": word["id"], "answer": word["english"]},
            )
        assert seen == {word["id"] for word in selected_words}

        assert client.get(
            f"/api/training/{training['id']}/solution/{outside_word['id']}"
        ).status_code == 404
        assert client.post(
            f"/api/training/{training['id']}/answers",
            json={"vocabulary_id": uncategorized["id"], "answer": "house"},
        ).status_code == 404


def test_training_requires_at_least_one_selected_category(tmp_path):
    with make_client(tmp_path) as client:
        folder = client.post("/api/folders", json={"name": "Leere Auswahl"}).json()
        client.post(
            f"/api/folders/{folder['id']}/vocabulary",
            json={"german": "Hund", "english": "dog", "category": "Tiere"},
        )

        response = client.post(
            "/api/training",
            json={
                "folder_id": folder["id"],
                "game_mode": "de-en",
                "categories": [],
                "include_uncategorized": False,
            },
        )
        assert response.status_code == 400


def test_csv_preview_skips_duplicates_and_reports_bad_rows(tmp_path):
    with make_client(tmp_path) as client:
        folder = client.post("/api/folders", json={"name": "CSV"}).json()
        client.post(
            f"/api/folders/{folder['id']}/vocabulary",
            json={"german": "Hund", "english": "dog"},
        )
        csv_file = io.BytesIO(
            "deutsch;englisch\nHund;dog\nKatze;cat\nPferd;\n".encode("utf-8")
        )
        preview = client.post(
            f"/api/folders/{folder['id']}/import/preview",
            files={"file": ("words.csv", csv_file, "text/csv")},
        ).json()
        assert preview["found"] == 3
        assert preview["valid"] == 1
        assert preview["duplicates"] == 1
        assert len(preview["errors"]) == 1

        imported = client.post(
            f"/api/folders/{folder['id']}/import", json={"rows": preview["rows"]}
        ).json()
        assert imported["imported"] == 1
        exported = client.get(f"/api/folders/{folder['id']}/export")
        assert "Katze;cat" in exported.text


def test_csv_preview_requires_semicolon_separator(tmp_path):
    with make_client(tmp_path) as client:
        folder = client.post("/api/folders", json={"name": "Trennzeichen"}).json()
        csv_file = io.BytesIO("deutsch,englisch\nHund,dog\n".encode("utf-8"))
        response = client.post(
            f"/api/folders/{folder['id']}/import/preview",
            files={"file": ("words.csv", csv_file, "text/csv")},
        )
        assert response.status_code == 400


def test_folder_deletion_removes_its_words_and_sessions(tmp_path):
    with make_client(tmp_path) as client:
        folder = client.post("/api/folders", json={"name": "Wegwerfmappe"}).json()
        client.post(
            f"/api/folders/{folder['id']}/vocabulary",
            json={"german": "Hund", "english": "dog"},
        )
        assert client.delete(f"/api/folders/{folder['id']}").status_code == 204
        assert client.get(f"/api/folders/{folder['id']}/vocabulary").status_code == 404
