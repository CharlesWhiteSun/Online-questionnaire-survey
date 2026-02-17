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
    "已成功儲存。系統會依照部門與訪談人員判斷為更新或新增。": "Saved successfully. The system decides whether to update or create based on Department and Interviewee.",
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
    "其他：": "Other:",
    "提交時間": "Submitted",
    "部門": "Department",
    "訪談人員": "Interviewee",
    "主測系統": "Primary System",
    "主測角色": "Primary Role",
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
            "footer_provider": "Provided by: Charles",
            "footer_contact": "If you have any requirements, please feel free to contact me.",
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
        "footer_provider": "提供者: Charles",
        "footer_contact": "若有任何需求，請不吝與我聯繫",
    }


def build_admin_ui_texts(lang: str) -> dict:
    if lang == "en":
        return {
            "page_title": "Admin Report",
            "total_submissions": "Total Submissions",
            "department_count": "Departments",
            "latest_submitted_at": "Latest Submitted At",
            "basic_section": "Basic Information",
            "questionnaire_section": "Questionnaire Details",
            "empty_text": "No submissions yet. Please submit the survey first.",
            "tag_submitted": "Submitted",
            "tag_department": "Department",
            "tag_person": "Interviewee",
            "tag_system": "Primary System",
            "tag_role": "Primary Role",
            "filter_date_label": "Filter by Date",
            "filter_apply": "Apply",
            "filter_reset": "Reset",
            "filter_selected_date": "Selected Date",
            "filter_no_match": "No records for the selected date.",
            "detail_panel_title": "Detailed Questionnaire",
            "detail_panel_hint": "Click a compact card above to view details here.",
            "compact_panel_title": "Compact Questionnaire List",
            "compact_panel_toggle": "Collapse list",
            "detail_panel_toggle": "Collapse details",
            "per_page_label": "Rows per page",
            "page_label": "Page",
            "prev_page": "Prev",
            "next_page": "Next",
            "data_export": "Export",
            "data_import": "Import",
            "delete_aria": "Delete this record",
            "delete_confirm_template": "Are you sure you want to delete the data for Department {department}, Interviewee {person}?",
            "unknown_text": "Unknown",
            "lang_zh": "中文",
            "lang_en": "EN",
            "footer_provider": "Provided by: Charles",
            "footer_contact": "If you have any requirements, please feel free to contact me.",
        }

    return {
        "page_title": "管理者報表",
        "total_submissions": "提交總筆數",
        "department_count": "部門數",
        "latest_submitted_at": "最新提交時間",
        "basic_section": "基本資料",
        "questionnaire_section": "問卷內容",
        "empty_text": "目前沒有提交資料，可先填寫問卷後再查看此頁。",
        "tag_submitted": "提交時間",
        "tag_department": "部門",
        "tag_person": "訪談人員",
        "tag_system": "主測系統",
        "tag_role": "主測角色",
        "filter_date_label": "依日期篩選",
        "filter_apply": "套用",
        "filter_reset": "清除",
        "filter_selected_date": "已選日期",
        "filter_no_match": "所選日期目前沒有資料。",
        "detail_panel_title": "詳細問卷內容",
        "detail_panel_hint": "請點選上方簡要卡片以查看詳細資料。",
        "compact_panel_title": "簡要問卷列表",
        "compact_panel_toggle": "收合列表",
        "detail_panel_toggle": "收合內容",
        "per_page_label": "每頁筆數",
        "page_label": "頁次",
        "prev_page": "上一頁",
        "next_page": "下一頁",
        "data_export": "匯出",
        "data_import": "匯入",
        "delete_aria": "刪除此筆資料",
        "delete_confirm_template": "確認要刪除此 {department} 部門 {person} 人員的資料嗎?",
        "unknown_text": "未知",
        "lang_zh": "中文",
        "lang_en": "EN",
        "footer_provider": "提供者: Charles",
        "footer_contact": "若有任何需求，請不吝與我聯繫",
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
    if lang == "en":
        return value.strftime("%b %d, %Y")
    return value.strftime("%Y/%m/%d")


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
                "options": field.get("options", []),
            }
        )

    return definition


REPORT_DEFINITION = build_report_definition()


def format_report_datetime(value: str, lang: str = "zh-TW") -> str:
    try:
        parsed = datetime.fromisoformat(value)
        return f"{format_date_by_lang(parsed, lang)} {parsed.strftime('%H:%M:%S')}"
    except ValueError:
        return value


def normalize_option_key(value: str) -> str:
    key = str(value).strip()
    for token in ["→", "-", "—", "（", "）", "(", ")", "/", " ", "	", "\n", "：", ":", "_", "\u3000"]:
        key = key.replace(token, "")
    return key.lower()


def canonicalize_selected_option(entry: dict, raw_value: str) -> str:
    options = entry.get("options", [])
    if not options:
        return raw_value

    raw_norm = normalize_option_key(raw_value)
    if not raw_norm:
        return raw_value

    for option in options:
        if raw_value == option:
            return option
        if raw_norm == normalize_option_key(option):
            return option

    return raw_value


def format_report_value(entry: dict, answers: dict, lang: str) -> str:
    value_parts = build_report_value_parts(entry, answers, lang)
    if entry["type"] == "multiselect":
        return "；".join(value_parts) if value_parts else "—"
    return value_parts[0] if value_parts else "—"


def build_report_value_parts(entry: dict, answers: dict, lang: str) -> list[str]:
    if entry["type"] == "multiselect":
        selected = answers.get(entry["name"], [])
        if not isinstance(selected, list):
            selected = [str(selected)] if str(selected).strip() else []
        selected_values = []
        for item in selected:
            raw_item = str(item).strip()
            if not raw_item:
                continue
            canonical_item = canonicalize_selected_option(entry, raw_item)
            selected_values.append(tr(canonical_item, lang))

        if entry.get("allow_other"):
            other_value = str(answers.get(f"{entry['name']}_other", "")).strip()
            if other_value:
                selected_values.append(f"{tr('其他：', lang)} {other_value}")

        return selected_values

    text_value = str(answers.get(entry["name"], "")).strip()
    return [tr(text_value, lang)] if text_value else []


def split_question_index_and_text(label: str) -> tuple[str, str]:
    matched = re.match(r"^(?P<idx>\d+(?:-\d+)?)\.\s*(?P<text>.+)$", str(label).strip())
    if not matched:
        return "", str(label)
    return matched.group("idx"), matched.group("text")


def get_report_records(lang: str = "zh-TW") -> list[dict]:
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
        submitted_raw = str(row[2])
        submitted_date = "—"
        submitted_time = "—"
        submitted_display = format_report_datetime(submitted_raw, lang)
        try:
            submitted_dt = datetime.fromisoformat(submitted_raw)
            submitted_date = submitted_dt.strftime("%Y-%m-%d")
            submitted_time = submitted_dt.strftime("%H:%M:%S")
        except ValueError:
            if " " in submitted_display:
                date_part, time_part = submitted_display.split(" ", 1)
                if len(date_part) == 10 and "-" in date_part:
                    submitted_date = date_part
                if len(time_part) >= 8:
                    submitted_time = time_part[:8]

        try:
            answers = json.loads(row[1])
        except json.JSONDecodeError:
            answers = {}

        basic_items = []
        questionnaire_items = []
        for entry in REPORT_DEFINITION:
            chips = build_report_value_parts(entry, answers, lang)
            question_index, question_text = split_question_index_and_text(tr(entry["label"], lang))
            item = {
                "label": tr(entry["label"], lang),
                "value": format_report_value(entry, answers, lang),
                "chips": chips if chips else ["—"],
                "question_index": question_index,
                "question_text": question_text,
            }
            if entry["section"] == "basic":
                basic_items.append(item)
            else:
                questionnaire_items.append(item)

        records.append(
            {
                "id": row[0],
                "submitted_at": submitted_display,
                "submitted_date": submitted_date,
                "submitted_time": submitted_time,
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


def filter_records_by_date(records: list[dict], selected_date: str) -> list[dict]:
    if not selected_date:
        return records
    return [record for record in records if record.get("submitted_date") == selected_date]


def build_available_dates(records: list[dict]) -> list[str]:
    return sorted(
        {record.get("submitted_date", "") for record in records if record.get("submitted_date") and record.get("submitted_date") != "—"},
        reverse=True,
    )


def normalize_positive_int(raw_value: str | None, default_value: int) -> int:
    try:
        parsed = int(str(raw_value))
        return parsed if parsed > 0 else default_value
    except (TypeError, ValueError):
        return default_value


def paginate_records(records: list[dict], page: int, per_page: int) -> tuple[list[dict], int, int]:
    total = len(records)
    if total == 0:
        return [], 1, 1

    total_pages = (total + per_page - 1) // per_page
    current_page = min(max(page, 1), total_pages)
    start = (current_page - 1) * per_page
    end = start + per_page
    return records[start:end], current_page, total_pages


def format_filter_date_value(selected_date: str, lang: str) -> str:
    if not selected_date:
        return ""
    try:
        parsed = datetime.strptime(selected_date, "%Y-%m-%d")
        return format_date_by_lang(parsed, lang)
    except ValueError:
        return selected_date


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
        row.extend(format_report_value(entry, record["answers"], "zh-TW") for entry in detail_entries)
        writer.writerow(row)

    return "\ufeff" + output.getvalue()


def normalize_import_submitted_at(value: str) -> str:
    raw_value = str(value).strip()
    if not raw_value or raw_value == "—":
        return now().isoformat(timespec="seconds")

    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"]:
        try:
            return datetime.strptime(raw_value, fmt).isoformat(timespec="seconds")
        except ValueError:
            continue
    return now().isoformat(timespec="seconds")


def split_multiselect_import_value(value: str) -> tuple[list[str], str]:
    text = str(value).strip()
    if not text or text == "—":
        return [], ""

    selected: list[str] = []
    other_value = ""
    for part in [item.strip() for item in text.split("；") if item.strip()]:
        if part.startswith("其他："):
            other_value = part.replace("其他：", "", 1).strip()
            continue
        if part.lower().startswith("other:"):
            other_value = part.split(":", 1)[1].strip() if ":" in part else ""
            continue
        selected.append(part)

    return selected, other_value


def import_report_csv(csv_text: str) -> int:
    content = str(csv_text).lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        return 0

    import_count = 0
    detail_entry_map = {entry["label"]: entry for entry in REPORT_DEFINITION}

    for row in reader:
        if not row:
            continue

        answers: dict = {
            "department_name": str(row.get("訪談部門", "")).strip(),
            "person_name": str(row.get("訪談人員", "")).strip(),
            "main_system": str(row.get("主測系統", "")).strip(),
            "main_role": str(row.get("主測角色", "")).strip(),
        }

        for label, entry in detail_entry_map.items():
            raw_value = str(row.get(label, "")).strip()
            if entry["type"] == "multiselect":
                selected_values, other_value = split_multiselect_import_value(raw_value)
                canonical_values = [canonicalize_selected_option(entry, value) for value in selected_values]
                answers[entry["name"]] = canonical_values
                if entry.get("allow_other"):
                    answers[f"{entry['name']}_other"] = other_value
            else:
                answers[entry["name"]] = "" if raw_value == "—" else raw_value

        if not answers["department_name"] or not answers["person_name"]:
            continue

        submitted_at = normalize_import_submitted_at(str(row.get("提交時間", "")))
        save_response_record(answers, submitted_at)
        import_count += 1

    return import_count


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


def save_response_record(answers: dict, submitted_at: str | None = None) -> None:
    department_name = str(answers.get("department_name", "")).strip()
    person_name = str(answers.get("person_name", "")).strip()
    persisted_at = submitted_at or now().isoformat(timespec="seconds")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO responses (survey_slug, department_name, person_name, answers_json, submitted_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(survey_slug, department_name, person_name)
            DO UPDATE SET answers_json = excluded.answers_json,
                          submitted_at = excluded.submitted_at
            """,
            (SURVEY_SLUG, department_name, person_name, json.dumps(answers, ensure_ascii=False), persisted_at),
        )
        conn.commit()


def upsert_response(answers: dict) -> None:
    save_response_record(answers)


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
    lang = get_lang()
    admin_ui = build_admin_ui_texts(lang)
    selected_date = request.args.get("date", "").strip()
    page = normalize_positive_int(request.args.get("page"), 1)
    per_page = normalize_positive_int(request.args.get("per_page"), 10)
    allowed_per_page = [10, 20, 50]
    if per_page not in allowed_per_page:
        per_page = 10
    if not selected_date:
        selected_date = now().strftime("%Y-%m-%d")

    all_records = get_report_records(lang)
    available_dates = build_available_dates(all_records)

    records = filter_records_by_date(all_records, selected_date)
    paged_records, current_page, total_pages = paginate_records(records, page, per_page)
    summary = build_report_summary(records)
    selected_date_display = format_filter_date_value(selected_date, lang)

    response = make_response(
        render_template(
            "admin_report.html",
            html_lang=get_html_lang(lang),
            current_lang=lang,
            admin_ui=admin_ui,
            survey_title=tr(SURVEY_TITLE, lang),
            summary=summary,
            records=paged_records,
            selected_date=selected_date,
            selected_date_display=selected_date_display,
            available_dates=available_dates,
            current_page=current_page,
            total_pages=total_pages,
            per_page=per_page,
            allowed_per_page=allowed_per_page,
            export_url=url_for("admin_report_export_csv", lang=lang),
            export_pdf_url=url_for("admin_report_export_pdf", lang=lang),
            prev_page_url=url_for("admin_report", lang=lang, date=selected_date, page=max(current_page - 1, 1), per_page=per_page),
            next_page_url=url_for("admin_report", lang=lang, date=selected_date, page=min(current_page + 1, total_pages), per_page=per_page),
            lang_urls={
                "zh-TW": url_for("admin_report", lang="zh-TW", date=selected_date, page=current_page, per_page=per_page),
                "en": url_for("admin_report", lang="en", date=selected_date, page=current_page, per_page=per_page),
            },
        )
    )
    return apply_common_cookies(response, lang)


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


@app.post("/admin/report/import.csv")
def admin_report_import_csv():
    lang = get_lang()
    selected_date = request.form.get("date", "").strip()
    page = request.form.get("page", "1").strip()
    per_page = request.form.get("per_page", "10").strip()

    uploaded = request.files.get("import_file")
    if uploaded and uploaded.filename:
        payload = uploaded.read().decode("utf-8-sig", errors="ignore")
        import_report_csv(payload)

    return redirect(url_for("admin_report", lang=lang, date=selected_date, page=page, per_page=per_page))


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
