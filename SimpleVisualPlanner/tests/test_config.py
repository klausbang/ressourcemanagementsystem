"""Config-level behavior that doesn't fit any one feature area - see proposal id 8
("sharing this dev instance with someone on another network"): SECRET_KEY must be
overridable via environment variable before ever exposing this beyond localhost, since
the checked-in default is public the moment the repo is.
"""
from app import create_app


def test_secret_key_defaults_to_dev_value_when_env_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    app = create_app({"DATABASE": str(tmp_path / "test.db"), "TESTING": True})
    assert app.config["SECRET_KEY"] == "dev-secret-change-me"


def test_secret_key_reads_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "a-real-secret-from-the-environment")
    app = create_app({"DATABASE": str(tmp_path / "test.db"), "TESTING": True})
    assert app.config["SECRET_KEY"] == "a-real-secret-from-the-environment"
