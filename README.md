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

## 3) 問卷開放時間調整

目前在 `survey_config.py` 由 `default_window()` 自動計算 5 個工作天。
若要固定日期，可直接修改：
- `OPEN_START_AT`
- `OPEN_END_AT`

## 4) 資料儲存

- SQLite 資料庫檔：`survey.db`
- 表格：`responses`
- 以 `(survey_slug, client_token)` 唯一鍵覆寫更新

## 5) 依 PDF 轉入的問卷內容

題目已根據 `file/自動化測試導入 需求訪談表.pdf` 建立於 `survey_config.py` 的 `FORM_DEFINITION`。
