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
    survey_app.init_db()
    survey_app.app.config["TESTING"] = True
    return survey_app.app.test_client()


def test_canonicalize_selected_option_accepts_legacy_value():
    entry = {
        "options": [
            "登入→主功能操作→送出",
            "查詢→檢視→匯出",
        ]
    }

    canonical = survey_app.canonicalize_selected_option(entry, "登入主功能操作送出")

    assert canonical == "登入→主功能操作→送出"


def test_admin_report_renders_compact_parallel_cards(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    survey_app.upsert_response(_sample_answers("登入主功能操作送出"))

    response = client.get("/admin/report?lang=en")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Automation Testing Adoption PoC Needs Interview Form" in html
    assert 'class="record-grid"' in html
    assert 'class="record-card"' in html
    assert 'data-record-select=' in html
    assert 'id="detail-panel"' in html
    assert 'id="compact-list-body"' in html
    assert 'data-collapse-target="compact-list-body"' in html
    assert 'data-collapse-target="detail-panel-body"' in html
    assert 'class="basic-detail-table"' in html
    assert 'class="detail-title detail-title-basic"' in html
    assert 'class="detail-title detail-title-questionnaire"' in html
    assert '<th class="table-label" scope="col">' in html
    assert '<tbody>' in html
    assert 'record-detail-template-' in html
    assert 'renderRecordDetail(' in html
    assert 'const firstSelectable' not in html
    assert "Questionnaire Details" in html
    assert "background: #cf222e;" not in html


def test_export_csv_uses_normalized_value_without_crash(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    survey_app.upsert_response(_sample_answers("登入主功能操作送出"))

    response = client.get("/admin/report/export.csv")

    assert response.status_code == 200
    content = response.get_data(as_text=True)
    assert content.startswith("\ufeff")
    assert "登入→主功能操作→送出" in content


def test_admin_report_date_filter_only_shows_selected_date(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    timestamps = iter(
        [
            datetime(2026, 2, 16, 8, 59, 59),
            datetime(2026, 2, 17, 9, 0, 1),
        ]
    )
    monkeypatch.setattr(survey_app, "now", lambda: next(timestamps))

    first = _sample_answers("登入主功能操作送出")
    first["department_name"] = "QA"
    first["person_name"] = "小花"
    second = _sample_answers("登入主功能操作送出")
    second["department_name"] = "研發"
    second["person_name"] = "阿明"

    survey_app.upsert_response(first)
    survey_app.upsert_response(second)

    response = client.get("/admin/report?lang=zh-TW&date=2026-02-16")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'type="date" value="2026-02-16"' in html
    assert "已選日期: 2026/02/16" in html
    assert ">08:59:59<" in html
    assert ">QA<" in html
    assert ">小花<" in html
    assert "09:00:01" not in html
    assert "研發" not in html
    assert "阿明" not in html


def test_admin_report_english_date_format_in_summary(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    monkeypatch.setattr(survey_app, "now", lambda: datetime(2026, 2, 17, 9, 0, 1))
    survey_app.upsert_response(_sample_answers("登入主功能操作送出"))

    response = client.get("/admin/report?lang=en")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Feb 17, 2026 09:00:01" in html


def test_admin_report_english_selected_date_display(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    monkeypatch.setattr(survey_app, "now", lambda: datetime(2026, 2, 17, 9, 0, 1))
    survey_app.upsert_response(_sample_answers("登入主功能操作送出"))

    response = client.get("/admin/report?lang=en&date=2026-02-17")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Selected Date: Feb 17, 2026" in html
    assert 'type="date" value="2026-02-17"' in html


def test_admin_report_defaults_date_filter_to_today(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    monkeypatch.setattr(survey_app, "now", lambda: datetime(2026, 2, 17, 9, 0, 1))

    response = client.get("/admin/report?lang=zh-TW")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'type="date" value="2026-02-17"' in html
    assert "已選日期: 2026/02/17" in html


def test_bilingual_footer_on_survey_and_admin_pages(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    monkeypatch.setattr(survey_app, "is_survey_open", lambda: True)

    survey_zh = client.get("/q/at?lang=zh-TW")
    survey_en = client.get("/q/at?lang=en")
    admin_zh = client.get("/admin/report?lang=zh-TW")
    admin_en = client.get("/admin/report?lang=en")

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
