import csv
import io
import json
import os
import re
import sqlite3
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

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
LANG_COOKIE_NAME = "survey_lang"
DEFAULT_LANG = "zh-TW"
SUPPORTED_LANGS = {"zh-TW", "en"}

app = Flask(__name__)
INDEX_PATTERN = re.compile(r"^(?P<main>\d+)(?:-(?P<sub>\d+))?\.")

EN_TRANSLATIONS = {
    "自動化測試導入 PoC 需求訪談表": "Automation Testing Adoption PoC Needs Interview Form",
    "問卷填寫時間已結束": "Survey Submission Window Closed",
    "本問卷已超過填寫期限，系統已停止收件。若您仍需補填或更新內容，請聯繫問卷管理者協助重新開放。": "This survey is past its submission deadline and is no longer accepting responses. If you still need to submit or update your response, please contact the survey administrator to reopen it.",
    "已成功儲存。若您再次開啟同一連結並提交，系統會覆寫您先前的內容。": "Saved successfully.",
    "找不到問卷": "Survey not found",
    "其他：請填寫": "Other: please specify",
}


def tr(text: str, lang: str) -> str:
    if lang == "en":
        return EN_TRANSLATIONS.get(text, text)
    return text


def normalize_lang(raw_lang: str | None) -> str:
    if not raw_lang:
        return DEFAULT_LANG
    if raw_lang.lower().startswith("en"):
        return "en"
    return DEFAULT_LANG


def get_lang() -> str:
    query_lang = request.args.get("lang")
    if query_lang:
        lang = normalize_lang(query_lang)
        if lang in SUPPORTED_LANGS:
            return lang

    cookie_lang = request.cookies.get(LANG_COOKIE_NAME)
    if cookie_lang:
        lang = normalize_lang(cookie_lang)
        if lang in SUPPORTED_LANGS:
            return lang

    return DEFAULT_LANG


def get_html_lang(lang: str) -> str:
    return "en" if lang == "en" else "zh-Hant"


def build_ui_texts(lang: str) -> dict:
    if lang == "en":
        return {
            "basic_title": "Basic Information",
            "questionnaire_title": "Questionnaire Fields",
            "open_time_label": "Open Window",
            "record_update_hint": "The system updates records based on the two-column mapping of Department and Interviewee to prevent duplicate entries.",
            "other_placeholder": tr("其他：請填寫", lang),
            "submit_button": "Submit / Update",
            "back_to_form": "Back to Survey",
            "survey_label": "Survey",
            "lang_zh": "中文",
            "lang_en": "EN",
        }

    return {
        "basic_title": "基本資料",
        "questionnaire_title": "問卷欄位",
        "open_time_label": "開放時間",
        "record_update_hint": "系統會依照部門、訪談人員的雙欄位對應來更新資料，避免重複新增",
        "other_placeholder": "其他：請填寫",
        "submit_button": "送出/更新",
        "back_to_form": "回到問卷頁",
        "survey_label": "問卷",
        "lang_zh": "中文",
        "lang_en": "EN",
    }


def localize_form_definition(lang: str) -> list[dict]:
    localized = deepcopy(FORM_DEFINITION)
    for field in localized:
        if "label" in field:
            field["label"] = tr(field["label"], lang)
        if "placeholder" in field:
            field["placeholder"] = tr(field["placeholder"], lang)

        if field.get("type") == "text_pair":
            field["left"]["label"] = tr(field["left"]["label"], lang)
            field["left"]["placeholder"] = tr(field["left"]["placeholder"], lang)
            field["right"]["label"] = tr(field["right"]["label"], lang)
            field["right"]["placeholder"] = tr(field["right"]["placeholder"], lang)

        if field.get("type") == "multiselect":
            field["options"] = [tr(option, lang) for option in field["options"]]

    return localized


def format_date_by_lang(value: datetime, lang: str) -> str:
    return value.strftime("%b %d, %Y")


def format_time(value: datetime) -> str:
    return value.strftime("%H:%M")


def build_open_window_parts(lang: str) -> dict:
    return {
        "start_date": format_date_by_lang(OPEN_START_AT, lang),
        "start_time": format_time(OPEN_START_AT),
        "end_date": format_date_by_lang(OPEN_END_AT, lang),
        "end_time": format_time(OPEN_END_AT),
    }


def build_report_definition() -> list[dict]:
    definition = []
    for field in FORM_DEFINITION:
        section = field.get("section", "questionnaire")
        field_type = field["type"]

        if field_type == "text_pair":
            definition.append(
                {
                    "section": section,
                    "type": "text",
                    "name": field["left"]["name"],
                    "label": field["left"]["label"],
                }
            )
            definition.append(
                {
                    "section": section,
                    "type": "text",
                    "name": field["right"]["name"],
                    "label": field["right"]["label"],
                }
            )
            continue

        definition.append(
            {
                "section": section,
                "type": field_type,
                "name": field["name"],
                "label": field["label"],
                "allow_other": field.get("allow_other", False),
            }
        )

    return definition


REPORT_DEFINITION = build_report_definition()


def format_report_datetime(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value


def format_report_value(entry: dict, answers: dict) -> str:
    if entry["type"] == "multiselect":
        selected = answers.get(entry["name"], [])
        if not isinstance(selected, list):
            selected = [str(selected)] if str(selected).strip() else []
        selected_values = [str(item).strip() for item in selected if str(item).strip()]

        if entry.get("allow_other"):
            other_value = str(answers.get(f"{entry['name']}_other", "")).strip()
            if other_value:
                selected_values.append(f"其他：{other_value}")

        return "；".join(selected_values) if selected_values else "—"

    text_value = str(answers.get(entry["name"], "")).strip()
    return text_value if text_value else "—"


def get_report_records() -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT id, answers_json, submitted_at
            FROM responses
            WHERE survey_slug = ?
            ORDER BY submitted_at DESC
            """,
            (SURVEY_SLUG,),
        ).fetchall()

    records = []
    for row in rows:
        try:
            answers = json.loads(row[1])
        except json.JSONDecodeError:
            answers = {}

        basic_items = []
        questionnaire_items = []
        for entry in REPORT_DEFINITION:
            item = {"label": entry["label"], "value": format_report_value(entry, answers)}
            if entry["section"] == "basic":
                basic_items.append(item)
            else:
                questionnaire_items.append(item)

        records.append(
            {
                "id": row[0],
                "submitted_at": format_report_datetime(row[2]),
                "department_name": str(answers.get("department_name", "")).strip() or "—",
                "person_name": str(answers.get("person_name", "")).strip() or "—",
                "main_system": str(answers.get("main_system", "")).strip() or "—",
                "main_role": str(answers.get("main_role", "")).strip() or "—",
                "basic_items": basic_items,
                "questionnaire_items": questionnaire_items,
                "answers": answers,
            }
        )

    return records


def build_report_summary(records: list[dict]) -> dict:
    departments = {
        record["department_name"]
        for record in records
        if record["department_name"] and record["department_name"] != "—"
    }

    return {
        "total_submissions": len(records),
        "department_count": len(departments),
        "latest_submitted_at": records[0]["submitted_at"] if records else "—",
    }


def build_report_csv(records: list[dict]) -> str:
    basic_columns = ["提交時間", "訪談部門", "訪談人員", "主測系統", "主測角色"]
    excluded_basic_names = {"department_name", "person_name", "main_system", "main_role"}
    detail_entries = [
        entry
        for entry in REPORT_DEFINITION
        if entry["name"] not in excluded_basic_names
    ]

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(basic_columns + [entry["label"] for entry in detail_entries])

    for record in records:
        row = [
            record["submitted_at"],
            record["department_name"],
            record["person_name"],
            record["main_system"],
            record["main_role"],
        ]
        row.extend(format_report_value(entry, record["answers"]) for entry in detail_entries)
        writer.writerow(row)

    return "\ufeff" + output.getvalue()


def build_report_pdf(records: list[dict], summary: dict) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    pdf.setFont("STSong-Light", 11)

    page_width, page_height = A4
    left = 40
    y = page_height - 40

    pdf.setFont("STSong-Light", 14)
    pdf.drawString(left, y, f"管理者報表｜{SURVEY_TITLE}")
    y -= 24

    pdf.setFont("STSong-Light", 10)
    pdf.drawString(left, y, f"提交總筆數：{summary['total_submissions']}")
    y -= 16
    pdf.drawString(left, y, f"部門數：{summary['department_count']}")
    y -= 16
    pdf.drawString(left, y, f"最新提交時間：{summary['latest_submitted_at']}")
    y -= 24

    for idx, record in enumerate(records, start=1):
        lines = [
            f"[{idx}] 提交時間：{record['submitted_at']}",
            f"部門：{record['department_name']}｜訪談人員：{record['person_name']}",
            f"主測系統：{record['main_system']}｜主測角色：{record['main_role']}",
        ]

        for item in record["questionnaire_items"]:
            lines.append(f"- {item['label']}：{item['value']}")

        for line in lines:
            if y < 45:
                pdf.showPage()
                pdf.setFont("STSong-Light", 10)
                y = page_height - 40
            pdf.drawString(left, y, line[:120])
            y -= 14

        y -= 6

    pdf.save()
    return buffer.getvalue()


def print_startup_info() -> None:
    print("=" * 60)
    print(f"問卷：{SURVEY_TITLE}")
    print(f"開放時間：{OPEN_START_AT:%Y-%m-%d %H:%M} ~ {OPEN_END_AT:%Y-%m-%d %H:%M}")
    print(f"短網址路徑：http://<你的內網IP>:5000/q/{SURVEY_SLUG}")
    print("=" * 60)


def get_index_parts(label: str) -> tuple[str | None, str | None]:
    matched = INDEX_PATTERN.match(label.strip())
    if not matched:
        return None, None
    return matched.group("main"), matched.group("sub")


def build_questionnaire_rows(fields: list[dict]) -> list[list[dict]]:
    rows: list[list[dict]] = []
    pending_plain: list[dict] = []
    index = 0

    while index < len(fields):
        field = fields[index]
        main, sub = get_index_parts(field.get("label", ""))

        if sub is not None and main is not None:
            if pending_plain:
                rows.append(pending_plain)
                pending_plain = []

            group = [field]
            index += 1
            while index < len(fields):
                next_field = fields[index]
                next_main, next_sub = get_index_parts(next_field.get("label", ""))
                if next_sub is None or next_main != main:
                    break
                group.append(next_field)
                index += 1

            for start in range(0, len(group), 2):
                rows.append(group[start : start + 2])
            continue

        pending_plain.append(field)
        if len(pending_plain) == 2:
            rows.append(pending_plain)
            pending_plain = []
        index += 1

    if pending_plain:
        rows.append(pending_plain)

    return rows


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        existing_columns = conn.execute("PRAGMA table_info(responses)").fetchall()
        if existing_columns:
            expected_columns = {
                "id",
                "survey_slug",
                "department_name",
                "person_name",
                "answers_json",
                "submitted_at",
            }
            current_columns = {column[1] for column in existing_columns}
            if current_columns != expected_columns:
                conn.execute("DROP TABLE responses")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                survey_slug TEXT NOT NULL,
                department_name TEXT NOT NULL,
                person_name TEXT NOT NULL,
                answers_json TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                UNIQUE(survey_slug, department_name, person_name)
            )
            """
        )
        conn.commit()


def now() -> datetime:
    return datetime.now()


def is_survey_open() -> bool:
    current = now()
    return OPEN_START_AT <= current <= OPEN_END_AT


def collect_answers(fields: list[dict]) -> dict:
    payload = {}
    for field in fields:
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


def upsert_response(answers: dict) -> None:
    department_name = str(answers.get("department_name", "")).strip()
    person_name = str(answers.get("person_name", "")).strip()
    submitted_at = now().isoformat(timespec="seconds")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO responses (survey_slug, department_name, person_name, answers_json, submitted_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(survey_slug, department_name, person_name)
            DO UPDATE SET answers_json = excluded.answers_json,
                          submitted_at = excluded.submitted_at
            """,
            (SURVEY_SLUG, department_name, person_name, json.dumps(answers, ensure_ascii=False), submitted_at),
        )
        conn.commit()


def apply_common_cookies(response, lang: str):
    response.set_cookie(LANG_COOKIE_NAME, lang, max_age=60 * 60 * 24 * 365)
    return response


@app.get("/")
def home():
    lang = get_lang()
    return redirect(url_for("survey", slug=SURVEY_SLUG, lang=lang))


@app.route("/q/<slug>", methods=["GET", "POST"])
def survey(slug: str):
    lang = get_lang()
    ui = build_ui_texts(lang)
    open_window_parts = build_open_window_parts(lang)

    if slug != SURVEY_SLUG:
        return tr("找不到問卷", lang), 404

    lang_urls = {
        "zh-TW": url_for("survey", slug=SURVEY_SLUG, lang="zh-TW"),
        "en": url_for("survey", slug=SURVEY_SLUG, lang="en"),
    }

    if not is_survey_open():
        response = make_response(
            render_template(
                "closed.html",
                html_lang=get_html_lang(lang),
                title=tr(CLOSED_MESSAGE_TITLE, lang),
                message=tr(CLOSED_MESSAGE_BODY, lang),
                survey_title=tr(SURVEY_TITLE, lang),
                open_window_parts=open_window_parts,
                ui=ui,
                lang_urls=lang_urls,
                current_lang=lang,
            ),
            410,
        )
        return apply_common_cookies(response, lang)

    localized_fields = localize_form_definition(lang)
    basic_fields = [field for field in localized_fields if field.get("section") == "basic"]
    questionnaire_fields = [field for field in localized_fields if field.get("section") != "basic"]
    questionnaire_rows = build_questionnaire_rows(questionnaire_fields)

    if request.method == "POST":
        answers = collect_answers(localized_fields)
        department_name = str(answers.get("department_name", "")).strip()
        person_name = str(answers.get("person_name", "")).strip()

        if not department_name or not person_name:
            response = make_response(
                render_template(
                    "form.html",
                    html_lang=get_html_lang(lang),
                    survey_title=tr(SURVEY_TITLE, lang),
                    basic_fields=basic_fields,
                    questionnaire_rows=questionnaire_rows,
                    existing=answers,
                    open_window_parts=open_window_parts,
                    ui=ui,
                    lang_urls=lang_urls,
                    current_lang=lang,
                    error_message="請先填寫訪談部門與訪談人員，系統才可判斷更新或新增。",
                )
            )
            return apply_common_cookies(response, lang)

        upsert_response(answers)

        response = make_response(
            render_template(
                "success.html",
                html_lang=get_html_lang(lang),
                survey_title=tr(SURVEY_TITLE, lang),
                message=tr(SUCCESS_MESSAGE, lang),
                survey_url=url_for("survey", slug=SURVEY_SLUG, lang=lang),
                ui=ui,
                lang_urls=lang_urls,
                current_lang=lang,
            )
        )
        return apply_common_cookies(response, lang)

    response = make_response(
        render_template(
            "form.html",
            html_lang=get_html_lang(lang),
            survey_title=tr(SURVEY_TITLE, lang),
            basic_fields=basic_fields,
            questionnaire_rows=questionnaire_rows,
            existing={},
            open_window_parts=open_window_parts,
            ui=ui,
            lang_urls=lang_urls,
            current_lang=lang,
            error_message="",
        )
    )
    return apply_common_cookies(response, lang)


@app.get("/admin/report")
def admin_report():
    records = get_report_records()
    summary = build_report_summary(records)

    return render_template(
        "admin_report.html",
        survey_title=SURVEY_TITLE,
        summary=summary,
        records=records,
        export_url=url_for("admin_report_export_csv"),
        export_pdf_url=url_for("admin_report_export_pdf"),
    )


@app.get("/admin/report/export.csv")
def admin_report_export_csv():
    records = get_report_records()
    payload = build_report_csv(records)
    filename = f"survey-report-{datetime.now():%Y%m%d-%H%M%S}.csv"

    response = make_response(payload)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@app.get("/admin/report/export.pdf")
def admin_report_export_pdf():
    records = get_report_records()
    summary = build_report_summary(records)
    payload = build_report_pdf(records, summary)
    filename = f"survey-report-{datetime.now():%Y%m%d-%H%M%S}.pdf"

    response = make_response(payload)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@app.post("/admin/report/delete/<int:record_id>")
def admin_report_delete_one(record_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM responses WHERE survey_slug = ? AND id = ?",
            (SURVEY_SLUG, record_id),
        )
        conn.commit()

    return redirect(url_for("admin_report"))


if __name__ == "__main__":
    init_db()
    print_startup_info()
    auto_reload = os.getenv("SURVEY_AUTO_RELOAD", "1") == "1"
    app.run(host="0.0.0.0", port=5000, debug=auto_reload, use_reloader=auto_reload)
