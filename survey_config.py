import json
from datetime import date, datetime, time, timedelta
from pathlib import Path


def add_workdays_including_start(start_date: date, workdays: int) -> date:
    current = start_date
    counted = 0
    while counted < workdays:
        if current.weekday() < 5:
            counted += 1
            if counted == workdays:
                break
        current += timedelta(days=1)
    return current


def default_window() -> tuple[datetime, datetime]:
    today = date.today()
    start = datetime.combine(today, time.min)
    end_date = add_workdays_including_start(today, 5)
    end = datetime.combine(end_date, time(23, 59, 59))
    return start, end


def load_window_from_param_file() -> tuple[datetime, datetime]:
    config_path = Path(__file__).parent / "survey_window.json"
    if not config_path.exists():
        return default_window()

    try:
        with config_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        start = datetime.strptime(payload["open_start_at"], "%Y-%m-%d %H:%M")
        end = datetime.strptime(payload["open_end_at"], "%Y-%m-%d %H:%M")
        if end < start:
            return default_window()
        return start, end
    except (json.JSONDecodeError, KeyError, ValueError):
        return default_window()


SURVEY_SLUG = "at"
SURVEY_TITLE = "自動化測試導入 PoC 需求訪談表"

OPEN_START_AT, OPEN_END_AT = load_window_from_param_file()

CLOSED_MESSAGE_TITLE = "問卷填寫時間已結束"
CLOSED_MESSAGE_BODY = (
    "本問卷已超過填寫期限，系統已停止收件。"
    "若您仍需補填或更新內容，請聯繫問卷管理者協助重新開放。"
)

SUCCESS_MESSAGE = "已成功儲存。若您再次開啟同一連結並提交，系統會覆寫您先前的內容。"

FORM_DEFINITION = [
    {
        "section": "basic",
        "type": "text_pair",
        "name": "department_person_pair",
        "label": "訪談部門/人員",
        "left": {
            "name": "department_name",
            "label": "訪談部門",
            "placeholder": "例如：研發部",
        },
        "right": {
            "name": "person_name",
            "label": "訪談人員",
            "placeholder": "例如：王小明",
        },
    },
    {
        "section": "basic",
        "type": "text_pair",
        "name": "main_system_role_pair",
        "label": "主測系統/角色",
        "left": {
            "name": "main_system",
            "label": "主測系統",
            "placeholder": "例如：ERP",
        },
        "right": {
            "name": "main_role",
            "label": "主測角色",
            "placeholder": "例如：審核者",
        },
    },
    {
        "type": "multiselect",
        "name": "core_flows",
        "label": "1. 自動化核心流程",
        "options": [
            "登入→主功能操作→送出",
            "查詢→檢視→匯出",
            "新增→送審→審核完成",
            "編輯→儲存→結果確認",
        ],
        "allow_other": True,
    },
    {
        "type": "multiselect",
        "name": "test_types",
        "label": "2. 測試類型需求",
        "options": [
            "Web UI 黑箱流程測試（End-to-End）",
            "多角色權限測試（Admin/User）",
            "API 測試（非 UI）",
            "效能測試（壓力/負載）",
            "安全測試（弱掃/登入防護）",
        ],
        "allow_other": True,
    },
    {
        "type": "multiselect",
        "name": "scenarios",
        "label": "3. 操作情境需求",
        "options": [
            "驗證碼（Captcha）",
            "OTP/簡訊驗證",
            "SSO/第三方登入",
            "多步驟表單",
            "彈跳視窗",
            "多頁籤操作",
            "檔案上傳",
            "Excel/PDF 匯出",
        ],
        "allow_other": True,
    },
    {
        "type": "multiselect",
        "name": "run_frequency",
        "label": "4-1. 測試執行頻率",
        "options": ["改版前", "每日定期跑", "手動觸發即可", "需可指定 tag 版本驗證"],
        "allow_other": True,
    },
    {
        "type": "multiselect",
        "name": "run_environment",
        "label": "4-2. 測試執行環境",
        "options": ["測試環境（Demo）", "驗收環境（UAT）", "正式環境（Prod）", "本機即可"],
        "allow_other": True,
    },
    {
        "type": "multiselect",
        "name": "browser_targets",
        "label": "5-1. 瀏覽器需求",
        "options": ["Chrome", "Edge", "Firefox", "Safari"],
        "allow_other": True,
    },
    {
        "type": "multiselect",
        "name": "device_targets",
        "label": "5-2. 裝置需求",
        "options": ["PC Web", "Mobile Web/APP", "需跨解析度測試"],
        "allow_other": True,
    },
    {
        "type": "multiselect",
        "name": "roles",
        "label": "6-1. 測試角色需求",
        "options": ["一般使用者", "管理者 Admin", "審核者 Reviewer", "多部門角色切換"],
        "allow_other": True,
    },
    {
        "type": "multiselect",
        "name": "account_method",
        "label": "6-2. 帳號方式",
        "options": ["使用系統內建帳號", "提供固定測試帳號", "測試工具需自動建立帳號"],
        "allow_other": True,
    },
    {
        "type": "multiselect",
        "name": "report_needs",
        "label": "7. 報告與管理需求",
        "options": [
            "自動測試報告（Pass/Fail）",
            "測試截圖紀錄",
            "測試影片錄製",
            "回歸測試覆蓋清單",
            "管理者摘要報表",
        ],
        "allow_other": True,
    },
    {
        "type": "multiselect",
        "name": "integrations",
        "label": "8. 整合需求",
        "options": ["Github", "Email 通知", "API"],
        "allow_other": True,
    },
    {
        "type": "multiselect",
        "name": "poc_scope",
        "label": "9-1. PoC 規模選擇",
        "options": [
            "單一流程驗證（1 條流程即可）",
            "小型流程組合（2–3 條核心流程）",
            "單一模組回歸測試（5–10 條案例）",
            "跨模組整合流程（包含多部門操作）",
            "全系統自動化（不建議 PoC）",
        ],
        "allow_other": True,
    },
    {
        "type": "multiselect",
        "name": "poc_acceptance",
        "label": "9-2. PoC 驗收標準",
        "options": [
            "核心流程可穩定重複執行",
            "改版後可快速回歸驗證",
            "測試結果可產出報告",
            "團隊可自行維護腳本",
            "可作為後續擴大導入基礎",
        ],
        "allow_other": True,
    },
    {
        "type": "textarea",
        "name": "notes",
        "label": "補充說明",
        "placeholder": "可填寫其他需求、限制或補充背景",
    },
]
