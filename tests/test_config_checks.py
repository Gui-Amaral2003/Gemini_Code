from pathlib import Path

from gemini.config_checks import CheckStatus, run_local_checks


def fake_finder(available=()):
    modules = set(available)
    return lambda name: object() if name in modules else None


def find_check(checks, group, name):
    return next(check for check in checks if check.group == group and check.name == name)


def test_empty_config_reports_required_gemini_and_skips_optional_groups(tmp_path):
    checks = run_local_checks({}, fake_finder(), tmp_path)

    assert find_check(checks, "Gemini", "API key").status is CheckStatus.ERROR
    assert find_check(checks, "SQL Server", "Integração").status is CheckStatus.SKIPPED
    assert find_check(checks, "Hive", "Integração").status is CheckStatus.SKIPPED
    assert find_check(checks, "Airflow", "Integração").status is CheckStatus.SKIPPED


def test_default_hive_port_alone_does_not_activate_integration(tmp_path):
    checks = run_local_checks(
        {"GEMINI_API_KEY": "real-key", "HIVE_PORT": "10000"},
        fake_finder({"google.genai"}),
        tmp_path,
    )

    assert find_check(checks, "Hive", "Integração").status is CheckStatus.SKIPPED


def test_partial_hive_config_reports_missing_variables_and_invalid_port(tmp_path):
    checks = run_local_checks(
        {"GEMINI_API_KEY": "real-key", "HIVE_HOST": "host", "HIVE_PORT": "70000"},
        fake_finder({"google.genai", "pyhive", "thrift"}),
        tmp_path,
    )

    variables = find_check(checks, "Hive", "Variáveis")
    assert variables.status is CheckStatus.ERROR
    assert "HIVE_PASSWORD" in variables.message
    assert find_check(checks, "Hive", "Porta").status is CheckStatus.ERROR


def test_airflow_http_url_is_warning_and_does_not_expose_credentials(tmp_path):
    secret = "senha-que-nao-pode-aparecer"
    checks = run_local_checks(
        {
            "GEMINI_API_KEY": "real-key",
            "AIRFLOW_API_URL": "http://airflow.internal:8080",
            "AIRFLOW_USERNAME": "usuario",
            "AIRFLOW_PASSWORD": secret,
        },
        fake_finder({"google.genai", "requests"}),
        tmp_path,
    )

    assert find_check(checks, "Airflow", "URL").status is CheckStatus.WARNING
    assert secret not in " ".join(check.message for check in checks)
    assert "airflow.internal" not in " ".join(check.message for check in checks)


def test_configured_dependency_is_reported_missing(tmp_path):
    checks = run_local_checks(
        {"GEMINI_API_KEY": "real-key", "DB_CONN_STRING": "driver=value"},
        fake_finder({"google.genai", "sqlalchemy"}),
        tmp_path,
    )

    assert find_check(checks, "SQL Server", "pyodbc").status is CheckStatus.ERROR


def test_output_parent_can_be_used_when_directory_does_not_exist(tmp_path):
    checks = run_local_checks(
        {"GEMINI_API_KEY": "real-key"},
        fake_finder({"google.genai"}),
        tmp_path / "future-output",
    )

    output = find_check(checks, "Sistema local", "Output")
    assert output.status is CheckStatus.OK
    assert "pode ser criado" in output.message
