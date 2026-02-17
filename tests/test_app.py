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
