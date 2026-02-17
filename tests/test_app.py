import io
from datetime import datetime

import app as survey_app


def _sample_answers(core_flow_value: str) -> dict:
    return {
        "department_name": "研發部",
        "person_name": "王小明",
        "main_system": "ERP",
        "main_role": "審核者",
        "core_flows": [core_flow_value],
    }


def _build_client_with_temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_survey.db"
    monkeypatch.setattr(survey_app, "DB_PATH", db_path)
    monkeypatch.setenv("SURVEY_GUEST_USERNAME", "guest")
    monkeypatch.setenv("SURVEY_GUEST_PASSWORD", "guest")
    monkeypatch.setenv("SURVEY_ADMIN_USERNAME", "manager")
    monkeypatch.setenv("SURVEY_ADMIN_PASSWORD", "manager-pass")
    survey_app.init_db()
    survey_app.app.config["TESTING"] = True
    return survey_app.app.test_client()


def _login_report_user(client, username: str, password: str, lang: str = "en"):
    return client.post(
        f"/admin/login?lang={lang}",
        data={"username": username, "password": password, "next": f"/admin/report?lang={lang}"},
        follow_redirects=False,
    )


def test_canonicalize_selected_option_accepts_legacy_value():
    entry = {
        "options": [
            "登入→主功能操作→送出",
            "查詢→檢視→匯出",
        ]
    }

    canonical = survey_app.canonicalize_selected_option(entry, "登入主功能操作送出")

    assert canonical == "登入→主功能操作→送出"


def test_ensure_env_file_creates_from_example(tmp_path):
    env_path = tmp_path / ".env"
    example_path = tmp_path / ".env.example"
    example_content = "SURVEY_GUEST_USERNAME=guest\nSURVEY_GUEST_PASSWORD=guest\n"
    example_path.write_text(example_content, encoding="utf-8")

    created = survey_app.ensure_env_file(env_path, example_path)

    assert created is True
    assert env_path.read_text(encoding="utf-8") == example_content


def test_ensure_env_file_does_not_overwrite_existing(tmp_path):
    env_path = tmp_path / ".env"
    example_path = tmp_path / ".env.example"
    env_path.write_text("EXISTING=1\n", encoding="utf-8")
    example_path.write_text("EXISTING=2\n", encoding="utf-8")

    created = survey_app.ensure_env_file(env_path, example_path)

    assert created is False
    assert env_path.read_text(encoding="utf-8") == "EXISTING=1\n"


def test_admin_report_renders_compact_parallel_cards(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    survey_app.upsert_response(_sample_answers("登入主功能操作送出"))
    login_response = _login_report_user(client, "guest", "guest", "en")
    assert login_response.status_code == 302

    response = client.get("/admin/report?lang=en")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Automation Testing Adoption PoC Needs Interview Form" in html
    assert 'class="report-actions"' not in html
    assert 'class="filter-export-actions"' in html
    assert '>CSV<' in html
    assert '>PDF<' in html
    assert 'class="selected-date-actions"' not in html
    assert '>Export<' not in html
    assert '>Import<' not in html
    assert 'id="inline-import-file-input"' not in html
    assert 'id="inline-import-trigger"' not in html
    assert 'id="selected-import-file-input"' not in html
    assert 'id="selected-import-trigger"' not in html
    assert 'class="record-grid"' in html
    assert 'class="record-card"' in html
    assert 'id="per-page-select" name="per_page"' in html
    assert '<option value="10" selected>' in html
    assert "Page 1 / 1" in html
    assert 'data-record-select=' in html
    assert 'class="mini-chip mini-chip-time"' in html
    assert "🕒" in html
    assert "🏢" in html
    assert "📇" in html
    assert 'id="detail-panel"' in html
    assert 'id="compact-list-body"' in html
    assert 'data-collapse-target="compact-list-body"' in html
    assert 'data-collapse-target="detail-panel-body"' in html
    assert 'class="basic-detail-table"' in html
    assert 'class="questionnaire-detail-table"' in html
    assert 'class="question-index-chip"' in html
    assert 'class="detail-title detail-title-basic"' in html
    assert 'class="detail-title detail-title-questionnaire"' in html
    assert '<th class="table-label" scope="col">' in html
    assert '<tbody>' in html
    assert 'record-detail-template-' in html
    assert 'renderRecordDetail(' in html
    assert 'const firstSelectable' not in html
    assert "Questionnaire Details" in html
    assert "background: #cf222e;" not in html


def test_admin_report_shows_csv_pdf_for_special_admin(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    survey_app.upsert_response(_sample_answers("登入主功能操作送出"))

    login_response = _login_report_user(client, "manager", "manager-pass", "en")
    assert login_response.status_code == 302

    response = client.get("/admin/report?lang=en")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'class="filter-export-actions"' in html
    assert '>CSV<' in html
    assert '>PDF<' in html
    assert 'class="selected-date-actions"' in html
    assert '>Export<' in html
    assert '>Import<' in html
    assert '.admin-export-btn {' in html
    assert '.admin-import-btn {' in html
    assert '.inline-file-input {' in html
    assert 'display: none;' in html
    assert 'width: 56px;' in html
    assert 'height: 40px;' in html
    assert 'box-sizing: border-box;' in html
    assert 'class="export-btn admin-export-btn"' in html
    assert '/admin/report/export.csv' in html
    assert 'class="export-btn admin-import-btn" id="selected-import-trigger"' in html
    assert 'id="inline-import-file-input"' not in html
    assert 'id="inline-import-trigger"' not in html
    assert 'id="selected-import-file-input"' in html
    assert 'id="selected-import-trigger"' in html


def test_admin_report_has_logout_countdown_and_reset_for_authenticated_user(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    survey_app.upsert_response(_sample_answers("登入主功能操作送出"))

    login_response = _login_report_user(client, "guest", "guest", "zh-TW")
    assert login_response.status_code == 302

    response = client.get("/admin/report?lang=zh-TW")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="logout-countdown"' in html
    assert 'id="reset-logout-timer"' in html
    assert 'id="logout-form"' in html
    assert "自動登出倒數" in html
    assert "重製計時" in html
    assert html.find('class="auth-actions"') < html.find('class="lang-switch"')


def test_admin_report_countdown_does_not_reset_after_refresh(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    current_time = {"value": datetime(2026, 2, 17, 9, 0, 0)}
    monkeypatch.setattr(survey_app, "now", lambda: current_time["value"])

    login_response = _login_report_user(client, "guest", "guest", "en")
    assert login_response.status_code == 302

    current_time["value"] = datetime(2026, 2, 17, 9, 3, 0)
    response = client.get("/admin/report?lang=en")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "const timeoutSeconds = Number(420);" in html
    assert "if (remainingSeconds <= 0) {\n      logoutForm.submit();\n      return;\n    }" not in html


def test_admin_session_reset_endpoint_resets_remaining_seconds(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    current_time = {"value": datetime(2026, 2, 17, 9, 0, 0)}
    monkeypatch.setattr(survey_app, "now", lambda: current_time["value"])

    login_response = _login_report_user(client, "guest", "guest", "en")
    assert login_response.status_code == 302

    current_time["value"] = datetime(2026, 2, 17, 9, 5, 0)
    reset_response = client.post("/admin/session/reset")
    report_response = client.get("/admin/report?lang=en")

    assert reset_response.status_code == 200
    assert reset_response.get_json()["remaining_seconds"] == 600
    assert report_response.status_code == 200
    assert "const timeoutSeconds = Number(600);" in report_response.get_data(as_text=True)


def test_admin_login_page_hides_heading_and_keeps_lang_spacing(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)

    response = client.get("/admin/login?lang=zh-TW")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'class="top-row"' in html
    assert 'margin-bottom: 18px;' in html
    assert "<h1" not in html
    assert '>登入<' in html
    assert '登入報表' not in html


def test_export_csv_uses_normalized_value_without_crash(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    survey_app.upsert_response(_sample_answers("登入主功能操作送出"))

    login_response = _login_report_user(client, "manager", "manager-pass", "zh-TW")
    assert login_response.status_code == 302

    response = client.get("/admin/report/export.csv")

    assert response.status_code == 200
    content = response.get_data(as_text=True)
    assert content.startswith("\ufeff")
    assert "登入→主功能操作→送出" in content


def test_admin_report_date_filter_only_shows_selected_date(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    timestamps = [
        datetime(2026, 2, 16, 8, 59, 59),
        datetime(2026, 2, 17, 9, 0, 1),
        datetime(2026, 2, 17, 9, 0, 1),
        datetime(2026, 2, 17, 9, 0, 1),
        datetime(2026, 2, 17, 9, 0, 1),
    ]
    state = {"idx": 0}

    def fake_now():
        idx = state["idx"]
        if idx < len(timestamps):
            state["idx"] = idx + 1
            return timestamps[idx]
        return timestamps[-1]

    monkeypatch.setattr(survey_app, "now", fake_now)

    first = _sample_answers("登入主功能操作送出")
    first["department_name"] = "QA"
    first["person_name"] = "小花"
    second = _sample_answers("登入主功能操作送出")
    second["department_name"] = "研發"
    second["person_name"] = "阿明"

    survey_app.upsert_response(first)
    survey_app.upsert_response(second)
    login_response = _login_report_user(client, "guest", "guest", "zh-TW")
    assert login_response.status_code == 302

    response = client.get("/admin/report?lang=zh-TW&date=2026-02-16")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'type="date" value="2026-02-16"' in html
    assert "已選日期:" in html
    assert 'class="selected-date-chip">2026/02/16</span>' in html
    assert "🕒 08:59:59" in html
    assert "🏢 QA" in html
    assert "📇 小花" in html
    assert "09:00:01" not in html
    assert "研發" not in html
    assert "阿明" not in html


def test_admin_report_english_date_format_in_summary(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    monkeypatch.setattr(survey_app, "now", lambda: datetime(2026, 2, 17, 9, 0, 1))
    survey_app.upsert_response(_sample_answers("登入主功能操作送出"))
    login_response = _login_report_user(client, "guest", "guest", "en")
    assert login_response.status_code == 302

    response = client.get("/admin/report?lang=en")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Feb 17, 2026 09:00:01" in html


def test_admin_report_english_selected_date_display(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    monkeypatch.setattr(survey_app, "now", lambda: datetime(2026, 2, 17, 9, 0, 1))
    survey_app.upsert_response(_sample_answers("登入主功能操作送出"))
    login_response = _login_report_user(client, "guest", "guest", "en")
    assert login_response.status_code == 302

    response = client.get("/admin/report?lang=en&date=2026-02-17")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Selected Date:" in html
    assert 'class="selected-date-chip">Feb 17, 2026</span>' in html
    assert 'type="date" value="2026-02-17"' in html


def test_admin_report_defaults_date_filter_to_today(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    monkeypatch.setattr(survey_app, "now", lambda: datetime(2026, 2, 17, 9, 0, 1))
    login_response = _login_report_user(client, "guest", "guest", "zh-TW")
    assert login_response.status_code == 302

    response = client.get("/admin/report?lang=zh-TW")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'type="date" value="2026-02-17"' in html
    assert "已選日期:" in html
    assert 'class="selected-date-chip">2026/02/17</span>' in html


def test_admin_report_pagination_default_10_and_next_page(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    base_time = datetime(2026, 2, 17, 9, 0, 0)
    counter = {"value": 0}

    def fake_now():
        offset = counter["value"]
        counter["value"] += 1
        return base_time.replace(second=offset % 60)

    monkeypatch.setattr(survey_app, "now", fake_now)

    for idx in range(12):
        answers = _sample_answers("登入主功能操作送出")
        answers["department_name"] = f"Dept{idx}"
        answers["person_name"] = f"Person{idx}"
        survey_app.upsert_response(answers)
    login_response = _login_report_user(client, "guest", "guest", "en")
    assert login_response.status_code == 302

    page1 = client.get("/admin/report?lang=en&date=2026-02-17")
    page2 = client.get("/admin/report?lang=en&date=2026-02-17&page=2&per_page=10")

    assert page1.status_code == 200
    assert page2.status_code == 200

    html1 = page1.get_data(as_text=True)
    html2 = page2.get_data(as_text=True)

    assert 'id="per-page-select" name="per_page"' in html1
    assert '<option value="10" selected>' in html1
    assert "Page 1 / 2" in html1
    assert "Page 2 / 2" in html2


def test_admin_report_import_csv_endpoint(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    monkeypatch.setattr(survey_app, "now", lambda: datetime(2026, 2, 17, 9, 0, 1))

    login_response = _login_report_user(client, "manager", "manager-pass", "zh-TW")
    assert login_response.status_code == 302

    csv_content = (
        "提交時間,訪談部門,訪談人員,主測系統,主測角色\n"
        "2026-02-17 08:59:59,QA,小花,ERP,審核者\n"
    )
    response = client.post(
        "/admin/report/import.csv?lang=zh-TW",
        data={
            "date": "2026-02-17",
            "page": "1",
            "per_page": "10",
            "import_file": (io.BytesIO(csv_content.encode("utf-8")), "import.csv"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "🏢 QA" in html
    assert "📇 小花" in html


def test_admin_report_export_import_forbidden_without_login(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)

    export_response = client.get("/admin/report/export.csv")
    import_response = client.post(
        "/admin/report/import.csv",
        data={"import_file": (io.BytesIO(b"header\n"), "import.csv")},
        content_type="multipart/form-data",
    )

    assert export_response.status_code == 403
    assert import_response.status_code == 403


def test_admin_report_redirects_to_login_when_not_authenticated(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)

    response = client.get("/admin/report?lang=en", follow_redirects=False)

    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]


def test_guest_can_view_and_export_but_cannot_import(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    survey_app.upsert_response(_sample_answers("登入主功能操作送出"))

    login_response = _login_report_user(client, "guest", "guest", "en")
    report_response = client.get("/admin/report?lang=en")
    export_csv_response = client.get("/admin/report/export.csv")
    export_pdf_response = client.get("/admin/report/export.pdf")
    import_response = client.post(
        "/admin/report/import.csv",
        data={"import_file": (io.BytesIO(b"header\n"), "import.csv")},
        content_type="multipart/form-data",
    )

    assert login_response.status_code == 302
    assert report_response.status_code == 200
    assert export_csv_response.status_code == 200
    assert export_pdf_response.status_code == 200
    assert import_response.status_code == 403


def test_bilingual_footer_on_survey_and_admin_pages(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    monkeypatch.setattr(survey_app, "is_survey_open", lambda: True)

    survey_zh = client.get("/q/at?lang=zh-TW")
    survey_en = client.get("/q/at?lang=en")
    login_zh = _login_report_user(client, "guest", "guest", "zh-TW")
    login_en = _login_report_user(client, "guest", "guest", "en")
    admin_zh = client.get("/admin/report?lang=zh-TW")
    admin_en = client.get("/admin/report?lang=en")

    assert login_zh.status_code == 302
    assert login_en.status_code == 302
    assert survey_zh.status_code == 200
    assert survey_en.status_code == 200
    assert admin_zh.status_code == 200
    assert admin_en.status_code == 200

    survey_zh_html = survey_zh.get_data(as_text=True)
    survey_en_html = survey_en.get_data(as_text=True)
    admin_zh_html = admin_zh.get_data(as_text=True)
    admin_en_html = admin_en.get_data(as_text=True)

    assert survey_zh_html.count('class="page-footer-line"') >= 2
    assert survey_en_html.count('class="page-footer-line"') >= 2
    assert admin_zh_html.count('class="page-footer-line"') >= 2
    assert admin_en_html.count('class="page-footer-line"') >= 2
    assert 'class="page-footer-card"' in survey_zh_html
    assert 'class="page-footer-card"' in survey_en_html
    assert 'class="page-footer-card"' in admin_zh_html
    assert 'class="page-footer-card"' in admin_en_html

    assert "提供者: Charles" in survey_zh_html
    assert "若有任何需求，請不吝與我聯繫" in survey_zh_html
    assert "Provided by: Charles" in survey_en_html
    assert "If you have any requirements, please feel free to contact me." in survey_en_html

    assert "提供者: Charles" in admin_zh_html
    assert "若有任何需求，請不吝與我聯繫" in admin_zh_html
    assert "Provided by: Charles" in admin_en_html
    assert "If you have any requirements, please feel free to contact me." in admin_en_html
