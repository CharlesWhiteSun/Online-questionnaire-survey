import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, make_response, redirect, render_template, request, url_for

from survey_config import (
    CLOSED_MESSAGE_BODY,
    CLOSED_MESSAGE_TITLE,
    FORM_DEFINITION,
    OPEN_END_AT,
    OPEN_START_AT,
    SUCCESS_MESSAGE,
    SURVEY_SLUG,
    SURVEY_TITLE,
)

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "survey.db"
COOKIE_NAME = "survey_client_id"

app = Flask(__name__)


def print_startup_info() -> None:
    print("=" * 60)
    print(f"問卷：{SURVEY_TITLE}")
    print(f"開放時間：{OPEN_START_AT:%Y-%m-%d %H:%M} ~ {OPEN_END_AT:%Y-%m-%d %H:%M}")
    print(f"短網址路徑：http://<你的內網IP>:5000/q/{SURVEY_SLUG}")
    print("=" * 60)


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                survey_slug TEXT NOT NULL,
                client_token TEXT NOT NULL,
                answers_json TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                UNIQUE(survey_slug, client_token)
            )
            """
        )
        conn.commit()


def now() -> datetime:
    return datetime.now()


def is_survey_open() -> bool:
    current = now()
    return OPEN_START_AT <= current <= OPEN_END_AT


def get_client_token() -> str:
    token = request.cookies.get(COOKIE_NAME)
    return token if token else str(uuid.uuid4())


def get_existing_answers(client_token: str) -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT answers_json FROM responses WHERE survey_slug = ? AND client_token = ?",
            (SURVEY_SLUG, client_token),
        ).fetchone()

    if not row:
        return {}

    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return {}


def collect_answers() -> dict:
    payload = {}
    for field in FORM_DEFINITION:
        field_type = field["type"]
        name = field["name"]
        if field_type == "multiselect":
            payload[name] = request.form.getlist(name)
            if field.get("allow_other"):
                payload[f"{name}_other"] = request.form.get(f"{name}_other", "").strip()
        elif field_type == "text_pair":
            left_name = field["left"]["name"]
            right_name = field["right"]["name"]
            payload[left_name] = request.form.get(left_name, "").strip()
            payload[right_name] = request.form.get(right_name, "").strip()
        else:
            payload[name] = request.form.get(name, "").strip()
    return payload


def upsert_response(client_token: str, answers: dict) -> None:
    submitted_at = now().isoformat(timespec="seconds")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO responses (survey_slug, client_token, answers_json, submitted_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(survey_slug, client_token)
            DO UPDATE SET answers_json = excluded.answers_json,
                          submitted_at = excluded.submitted_at
            """,
            (SURVEY_SLUG, client_token, json.dumps(answers, ensure_ascii=False), submitted_at),
        )
        conn.commit()


@app.get("/")
def home():
    return redirect(url_for("survey", slug=SURVEY_SLUG))


@app.route("/q/<slug>", methods=["GET", "POST"])
def survey(slug: str):
    if slug != SURVEY_SLUG:
        return "找不到問卷", 404

    if not is_survey_open():
        return (
            render_template(
                "closed.html",
                title=CLOSED_MESSAGE_TITLE,
                message=CLOSED_MESSAGE_BODY,
                survey_title=SURVEY_TITLE,
                open_start=OPEN_START_AT,
                open_end=OPEN_END_AT,
            ),
            410,
        )

    client_token = get_client_token()

    if request.method == "POST":
        answers = collect_answers()
        upsert_response(client_token, answers)

        response = make_response(
            render_template(
                "success.html",
                survey_title=SURVEY_TITLE,
                message=SUCCESS_MESSAGE,
                survey_url=url_for("survey", slug=SURVEY_SLUG),
            )
        )
        response.set_cookie(COOKIE_NAME, client_token, max_age=60 * 60 * 24 * 365)
        return response

    existing_answers = get_existing_answers(client_token)
    response = make_response(
        render_template(
            "form.html",
            survey_title=SURVEY_TITLE,
            fields=FORM_DEFINITION,
            existing=existing_answers,
            open_start=OPEN_START_AT,
            open_end=OPEN_END_AT,
            short_path=url_for("survey", slug=SURVEY_SLUG),
        )
    )
    response.set_cookie(COOKIE_NAME, client_token, max_age=60 * 60 * 24 * 365)
    return response


if __name__ == "__main__":
    init_db()
    print_startup_info()
    app.run(host="0.0.0.0", port=5000, debug=False)
