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
- 以 `(survey_slug, client_token)` 唯一鍵覆寫更新

## 5) 欄位拆分

已調整為左右雙欄輸入：
- 訪談部門/人員 → `訪談部門` + `訪談人員`
- 主測系統/角色 → `主測系統` + `主測角色`

## 6) 依 PDF 轉入的問卷內容

題目已根據 `file/自動化測試導入 需求訪談表.pdf` 建立於 `survey_config.py` 的 `FORM_DEFINITION`。
