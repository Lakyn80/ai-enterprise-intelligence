from pathlib import Path

from app.settings import PROJECT_ROOT, Settings


def test_settings_use_repo_root_env_file():
    assert Path(Settings.model_config["env_file"]) == PROJECT_ROOT / ".env"


def test_settings_ignore_extra_env_keys_in_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=sqlite+aiosqlite:///tmp/test.db",
                "DEBUG=release",
                "NEXT_PUBLIC_API_URL=http://localhost:4000",
                "REDIS_HOST_PORT=6380",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.database_url == "sqlite+aiosqlite:///tmp/test.db"
    assert settings.debug is False


def test_settings_accept_debug_release_env_value(monkeypatch):
    monkeypatch.setenv("DEBUG", "release")

    settings = Settings(_env_file=None)

    assert settings.debug is False
