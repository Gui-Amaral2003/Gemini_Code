from io import StringIO

from rich.console import Console

from gemini import config_wizard
from gemini.env_config import EnvSetting


def make_console() -> Console:
    return Console(file=StringIO(), force_terminal=False, width=100)


def test_secret_setting_uses_hidden_prompt(monkeypatch):
    captured = {}
    saved = []
    setting = EnvSetting(
        key="SECRET",
        label="Segredo",
        group="Teste",
        secret=True,
    )

    def fake_ask(_label, **kwargs):
        captured.update(kwargs)
        return "valor-secreto"

    monkeypatch.setattr(config_wizard.Prompt, "ask", fake_ask)
    monkeypatch.setattr(
        config_wizard,
        "update_env_value",
        lambda key, value: saved.append((key, value)),
    )

    config_wizard._edit_setting(make_console(), setting, {})

    assert captured["password"] is True
    assert saved == [("SECRET", "valor-secreto")]


def test_empty_input_keeps_existing_value(monkeypatch):
    setting = EnvSetting(
        key="EXISTING",
        label="Existente",
        group="Teste",
    )
    monkeypatch.setattr(config_wizard.Prompt, "ask", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(
        config_wizard,
        "update_env_value",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("valor existente não deveria ser sobrescrito")
        ),
    )

    config_wizard._edit_setting(
        make_console(),
        setting,
        {"EXISTING": "valor-atual"},
    )


def test_invalid_value_is_prompted_again(monkeypatch):
    answers = iter(["invalid", "1234"])
    saved = []
    setting = EnvSetting(
        key="PORT",
        label="Porta",
        group="Teste",
        validator=lambda value: None if value.isdigit() else "Porta inválida.",
    )
    monkeypatch.setattr(
        config_wizard.Prompt,
        "ask",
        lambda *_args, **_kwargs: next(answers),
    )
    monkeypatch.setattr(
        config_wizard,
        "update_env_value",
        lambda key, value: saved.append((key, value)),
    )

    config_wizard._edit_setting(make_console(), setting, {})

    assert saved == [("PORT", "1234")]
