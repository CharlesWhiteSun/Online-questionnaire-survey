# 內部問卷調查系統（Flask + SQLite）

本系統提供公司內網使用的匿名問卷與管理報表，支援中英雙語、角色登入、匯出/匯入與自動測試。

## 1) 目前功能總覽

### 問卷端
- 匿名填答、免登入。
- 入口短網址：`/q/at`。
- 開放時間可設定，超過期限顯示截止頁。
- 提交採唯一鍵更新：`(survey_slug, department_name, person_name)`，同部門+人員會覆寫舊資料。
- 問卷與成功/截止頁皆支援 `zh-TW` / `en`。

### 報表端
- 路徑：`/admin/report`（需先登入）。
- 提供日期篩選、摘要卡（總筆數/部門數/最新時間）、卡片式列表與詳情區塊。
- 支援分頁與每頁筆數（10/20/50）。
- 管理者可刪除單筆資料。

### 登入與權限
- 登入頁：`/admin/login`。
- 角色分為 `guest`（一般使用者）與 `admin`（管理者）。
- `guest`：可查看報表、可使用 CSV/PDF 匯出。
- `admin`：擁有 `guest` 全部權限，另可使用「匯出/匯入」管理按鈕（匯入 CSV）。
- 登入後有 10 分鐘自動登出倒數。
	- 倒數由後端 session 剩餘秒數驅動，重新整理頁面不會重置。
	- 可按「重製計時」重設回 10 分鐘。

## 2) 安裝與啟動

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

預設監聽：
- `http://127.0.0.1:5000`
- 內網：`http://<你的內網IP>:5000`

開發自動重載：
- 開啟（預設）：`SURVEY_AUTO_RELOAD=1`
- 關閉：`SURVEY_AUTO_RELOAD=0`

PowerShell 範例：

```powershell
$env:SURVEY_AUTO_RELOAD="0"
python app.py
```

## 3) .env 設定（登入帳號密碼）

啟動時若根目錄沒有 `.env`，系統會自動由 `.env.example` 建立。

`.env` 範例：

```env
SURVEY_GUEST_USERNAME=guest
SURVEY_GUEST_PASSWORD=guest
SURVEY_ADMIN_USERNAME=manager
SURVEY_ADMIN_PASSWORD=請改成你的管理者密碼
```

> 建議首次啟動後立即修改 `SURVEY_ADMIN_PASSWORD`。

## 4) 問卷開放時間設定

請編輯 `survey_window.json`：

```json
{
	"open_start_at": "2026-02-16 09:00",
	"open_end_at": "2026-02-20 18:00"
}
```

- 時間格式：`YYYY-MM-DD HH:MM`
- 若格式錯誤或結束早於開始，系統會回退到預設開放窗。

## 5) 報表操作說明

- 一般匯出按鈕（CSV/PDF）：在日期篩選列右側。
- 管理者匯出/匯入按鈕：在「已選日期」列右側。
- 匯入流程：按「匯入」→ 選擇 `.csv` 檔案 → 自動送出。
- 匯出路由：
	- CSV：`/admin/report/export.csv`
	- PDF：`/admin/report/export.pdf`

## 6) 資料儲存

- 資料庫：`survey.db`（SQLite）
- 表格：`responses`
- 主鍵策略：以 `(survey_slug, department_name, person_name)` 做 upsert。

## 7) 自動化測試

```powershell
python -m pytest -q
```

目前測試包含：
- 權限控管（guest/admin/未登入）
- 報表按鈕顯示規則與版面回歸
- 倒數登出與重製計時
- 匯出/匯入路由與內容
- i18n 顯示與日期格式
