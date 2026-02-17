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


def test_admin_report_english_translates_title_and_normalized_value(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    survey_app.upsert_response(_sample_answers("登入主功能操作送出"))

    response = client.get("/admin/report?lang=en")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Automation Testing Adoption PoC Needs Interview Form" in html
    assert "Login → Main Action → Submit" in html
    assert "登入主功能操作送出" not in html


def test_export_csv_uses_normalized_value_without_crash(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    survey_app.upsert_response(_sample_answers("登入主功能操作送出"))

    response = client.get("/admin/report/export.csv")

    assert response.status_code == 200
    content = response.get_data(as_text=True)
    assert content.startswith("\ufeff")
    assert "登入→主功能操作→送出" in content


def test_admin_report_renders_section_cards_and_metric_chips(tmp_path, monkeypatch):
    client = _build_client_with_temp_db(tmp_path, monkeypatch)
    answers = _sample_answers("登入主功能操作送出")
    answers["core_flows"] = ["登入主功能操作送出", "查詢檢視匯出"]
    survey_app.upsert_response(answers)

    response = client.get("/admin/report?lang=en")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.count('class="section-card"') >= 2
    assert html.count('class="section-title"') >= 2
    assert html.count('class="section-body"') >= 2
    assert 'class="report-actions"' in html
    assert html.index('class="summary-grid"') < html.index('class="report-actions"')
    assert 'metric-chip metric-chip-basic' in html
    assert 'metric-chip metric-chip-questionnaire' in html
    assert 'class="metric-chip metric-chip-questionnaire">Login → Main Action → Submit</span>' in html
    assert 'class="metric-chip metric-chip-questionnaire">Search → View → Export</span>' in html
    assert "Login → Main Action → Submit；Search → View → Export" not in html


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

    assert "提供者: Charles" in survey_zh_html
    assert "若有任何需求，請不吝與我聯繫" in survey_zh_html
    assert "Provided by: Charles" in survey_en_html
    assert "If you have any requirements, please feel free to contact me." in survey_en_html

    assert "提供者: Charles" in admin_zh_html
    assert "若有任何需求，請不吝與我聯繫" in admin_zh_html
    assert "Provided by: Charles" in admin_en_html
    assert "If you have any requirements, please feel free to contact me." in admin_en_html
