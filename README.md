# 內部問卷調查系統（本機版）

此專案已依照需求建立：
- 匿名填答、無需登入
- 以短網址路徑開啟問卷
- 開放期限預設為「啟動當天起算 5 個工作天」
- 同一裝置重複送出時，採覆寫更新，不會新增多筆
- 期限過後顯示友善提示頁

## 1) 安裝

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2) 啟動

```powershell
python app.py
```

預設已啟用開發自動重啟（修改 Python/模板後會自動套用）：
- 啟用（預設）：`SURVEY_AUTO_RELOAD=1`
- 關閉：`SURVEY_AUTO_RELOAD=0`

PowerShell 臨時關閉範例：

```powershell
$env:SURVEY_AUTO_RELOAD="0"
python app.py
```

預設會監聽：
- `http://127.0.0.1:5000`
- 區網可用：`http://<你的內網IP>:5000`

建議短網址（內網）：
- `http://<你的內網IP>:5000/q/at`

## 3) 問卷開放時間調整（參數檔）

請編輯 `survey_window.json`：

```json
{
	"open_start_at": "2026-02-16 09:00",
	"open_end_at": "2026-02-20 18:00"
}
```

- 時間格式固定為 `YYYY-MM-DD HH:MM`
- 若格式錯誤或結束早於開始，系統會自動回退為「啟動當天起算 5 個工作天」

## 4) 資料儲存

- SQLite 資料庫檔：`survey.db`
- 表格：`responses`
- 以 `(survey_slug, department_name, person_name)` 唯一鍵覆寫更新

## 5) 欄位拆分

已調整為左右雙欄輸入：
- 訪談部門/人員 → `訪談部門` + `訪談人員`
- 主測系統/角色 → `主測系統` + `主測角色`

## 6) 依 PDF 轉入的問卷內容

題目已根據 `file/自動化測試導入 需求訪談表.pdf` 建立於 `survey_config.py` 的 `FORM_DEFINITION`。

## 7) 語系切換（i18n）

- 支援語系：`zh-TW`、`en`
- 頁首右上有語系切換按鈕（中文 / EN）
- 也可透過網址參數切換：
	- `http://<你的內網IP>:5000/q/at?lang=zh-TW`
	- `http://<你的內網IP>:5000/q/at?lang=en`

## 8) 報表登入、角色與匯出

- 報表頁：`http://<你的內網IP>:5000/admin/report`
- 登入頁：`http://<你的內網IP>:5000/admin/login`
- 報表頁現在需先登入（一般使用者與管理者都可登入查看）
- 一般使用者預設帳密：`guest / guest`
- 管理者帳密可透過根目錄 `.env` 設定

根目錄 `.env` 範例：

```env
SURVEY_GUEST_USERNAME=guest
SURVEY_GUEST_PASSWORD=guest
SURVEY_ADMIN_USERNAME=manager
SURVEY_ADMIN_PASSWORD=請改成你的管理者密碼
```

- 若啟動時找不到 `.env`，系統會自動用 `.env.example` 建立一份 `.env`
- 建立後請務必修改管理者密碼

- 一般使用者（guest）可查看報表
- 管理者（admin）可查看報表 + 匯出/匯入
- 匯出 CSV（管理者）：`http://<你的內網IP>:5000/admin/report/export.csv`
- 報表頁會顯示：提交總筆數、部門數、最新提交時間
- 每筆問卷以簡易卡片並排顯示（時間 / 部門 / 人員）
- 可用日期篩選（Date）快速查看指定日期的提交資料

## 9) 自動化測試（必跑）

每次修改程式碼（包含模板、共用函式、路由）前後，都應新增或更新對應測試，並執行完整測試避免破壞既有功能。

執行測試：

```powershell
python -m pytest -q
```

目前測試重點包含：
- 舊資料選項值正規化（例如：`登入主功能操作送出`）
- 英文管理頁標題與選項翻譯
- CSV 匯出路徑與內容正規化
