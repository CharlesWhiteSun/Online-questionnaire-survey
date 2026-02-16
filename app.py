import json
import re
import sqlite3
import uuid
from copy import deepcopy
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
LANG_COOKIE_NAME = "survey_lang"
DEFAULT_LANG = "zh-TW"
SUPPORTED_LANGS = {"zh-TW", "en"}

app = Flask(__name__)
INDEX_PATTERN = re.compile(r"^(?P<main>\d+)(?:-(?P<sub>\d+))?\.")

EN_TRANSLATIONS = {
    "自動化測試導入 PoC 需求訪談表": "Automation Testing Adoption PoC Needs Interview Form",
    "自動化測試導入需求訪談表": "Automation Testing Adoption Needs Interview Form",
    "問卷填寫時間已結束": "Survey Submission Window Closed",
    "本問卷已超過填寫期限，系統已停止收件。若您仍需補填或更新內容，請聯繫問卷管理者協助重新開放。": "This survey is past its submission deadline and is no longer accepting responses. If you still need to submit or update your response, please contact the survey administrator to reopen it.",
    "已成功儲存。若您再次開啟同一連結並提交，系統會覆寫您先前的內容。": "Saved successfully. If you submit again from the same link and device, your previous response will be overwritten.",
    "找不到問卷": "Survey not found",
    "訪談部門/人員": "Interview Department / Interviewee",
    "訪談部門": "Department",
    "例如：研發部": "e.g. Engineering Department",
    "訪談人員": "Interviewee",
    "例如：王小明": "e.g. Alex Wang",
    "主測系統/角色": "Primary System / Role",
    "主測系統": "Primary System",
    "例如：ERP": "e.g. ERP",
    "主測角色": "Primary Role",
    "例如：審核者": "e.g. Reviewer",
    "1. 自動化核心流程": "1. Automation Core Flows",
    "登入→主功能操作→送出": "Login → Main Action → Submit",
    "查詢→檢視→匯出": "Search → View → Export",
    "新增→送審→審核完成": "Create → Submit for Approval → Approved",
    "編輯→儲存→結果確認": "Edit → Save → Verify Result",
    "2. 測試類型需求": "2. Required Test Types",
    "Web UI 黑箱流程測試（End-to-End）": "Web UI Black-box Flow Testing (End-to-End)",
    "多角色權限測試（Admin/User）": "Multi-role Permission Testing (Admin/User)",
    "API 測試（非 UI）": "API Testing (Non-UI)",
    "效能測試（壓力/負載）": "Performance Testing (Stress/Load)",
    "安全測試（弱掃/登入防護）": "Security Testing (Vulnerability Scan/Login Protection)",
    "3. 操作情境需求": "3. Required Operation Scenarios",
    "驗證碼（Captcha）": "Captcha",
    "OTP/簡訊驗證": "OTP / SMS Verification",
    "SSO/第三方登入": "SSO / Third-party Login",
    "多步驟表單": "Multi-step Form",
    "彈跳視窗": "Pop-up Dialog",
    "多頁籤操作": "Multi-tab Operations",
    "檔案上傳": "File Upload",
    "Excel/PDF 匯出": "Excel/PDF Export",
    "4-1. 測試執行頻率": "4-1. Test Execution Frequency",
    "改版前": "Before Release",
    "每日定期跑": "Run Daily on Schedule",
    "手動觸發即可": "Manual Trigger is Enough",
    "需可指定 tag 版本驗證": "Need Validation by Specific Tag Version",
    "4-2. 測試執行環境": "4-2. Test Execution Environment",
    "測試環境（Demo）": "Testing Environment (Demo)",
    "驗收環境（UAT）": "User Acceptance Environment (UAT)",
    "正式環境（Prod）": "Production Environment (Prod)",
    "本機即可": "Local Machine is Enough",
    "5-1. 瀏覽器需求": "5-1. Browser Requirements",
    "Chrome": "Chrome",
    "Edge": "Edge",
    "Firefox": "Firefox",
    "Safari": "Safari",
    "5-2. 裝置需求": "5-2. Device Requirements",
    "PC Web": "PC Web",
    "Mobile Web/APP": "Mobile Web/APP",
    "需跨解析度測試": "Need Cross-resolution Testing",
    "6-1. 測試角色需求": "6-1. Test Role Requirements",
    "一般使用者": "General User",
    "管理者 Admin": "Administrator (Admin)",
    "審核者 Reviewer": "Reviewer",
    "多部門角色切換": "Multi-department Role Switching",
    "6-2. 帳號方式": "6-2. Account Setup",
    "使用系統內建帳號": "Use Built-in System Accounts",
    "提供固定測試帳號": "Provide Fixed Test Accounts",
    "測試工具需自動建立帳號": "Testing Tool Must Auto-create Accounts",
    "7. 報告與管理需求": "7. Reporting & Management Needs",
    "自動測試報告（Pass/Fail）": "Automated Test Report (Pass/Fail)",
    "測試截圖紀錄": "Test Screenshot Records",
    "測試影片錄製": "Test Video Recording",
    "回歸測試覆蓋清單": "Regression Coverage Checklist",
    "管理者摘要報表": "Manager Summary Report",
    "8. 整合需求": "8. Integration Needs",
    "Github": "GitHub",
    "Email 通知": "Email Notifications",
    "API": "API",
    "9-1. PoC 規模選擇": "9-1. PoC Scope Selection",
    "單一流程驗證（1 條流程即可）": "Single Flow Verification (1 flow)",
    "小型流程組合（2–3 條核心流程）": "Small Flow Set (2–3 core flows)",
    "單一模組回歸測試（5–10 條案例）": "Single Module Regression (5–10 cases)",
    "跨模組整合流程（包含多部門操作）": "Cross-module Integrated Flows (multi-department)",
    "全系統自動化（不建議 PoC）": "Full-system Automation (Not Recommended for PoC)",
    "9-2. PoC 驗收標準": "9-2. PoC Acceptance Criteria",
    "核心流程可穩定重複執行": "Core flows can run repeatedly and stably",
    "改版後可快速回歸驗證": "Fast regression validation after each release",
    "測試結果可產出報告": "Test results can generate reports",
    "團隊可自行維護腳本": "Team can maintain scripts independently",
    "可作為後續擴大導入基礎": "Can serve as a foundation for scaled adoption",
    "補充說明": "Additional Notes",
    "可填寫其他需求、限制或補充背景": "You can add other requirements, constraints, or background details",
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


def format_datetime_by_lang(value: datetime, lang: str) -> str:
    return value.strftime("%b %d, %Y %H:%M")


def build_open_window_text(lang: str) -> str:
    return f"{format_datetime_by_lang(OPEN_START_AT, lang)} ~ {format_datetime_by_lang(OPEN_END_AT, lang)}"



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



def apply_common_cookies(response, client_token: str, lang: str):
    response.set_cookie(COOKIE_NAME, client_token, max_age=60 * 60 * 24 * 365)
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
    open_window_text = build_open_window_text(lang)

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
                open_window_text=open_window_text,
                ui=ui,
                lang_urls=lang_urls,
                current_lang=lang,
            ),
            410,
        )
        return apply_common_cookies(response, get_client_token(), lang)

    client_token = get_client_token()
    localized_fields = localize_form_definition(lang)

    if request.method == "POST":
        answers = collect_answers(localized_fields)
        upsert_response(client_token, answers)

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
        return apply_common_cookies(response, client_token, lang)

    existing_answers = get_existing_answers(client_token)
    basic_fields = [field for field in localized_fields if field.get("section") == "basic"]
    questionnaire_fields = [field for field in localized_fields if field.get("section") != "basic"]
    questionnaire_rows = build_questionnaire_rows(questionnaire_fields)

    response = make_response(
        render_template(
            "form.html",
            html_lang=get_html_lang(lang),
            survey_title=tr(SURVEY_TITLE, lang),
            basic_fields=basic_fields,
            questionnaire_rows=questionnaire_rows,
            existing=existing_answers,
            open_window_text=open_window_text,
            ui=ui,
            lang_urls=lang_urls,
            current_lang=lang,
        )
    )
    return apply_common_cookies(response, client_token, lang)



if __name__ == "__main__":
    init_db()
    print_startup_info()
    app.run(host="0.0.0.0", port=5000, debug=False)
