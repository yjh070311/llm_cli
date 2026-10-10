import app.config
import pytest
from app.config import AppConfig, ConfigError, get_config


def _clear_config_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)


def test_get_config_reads_env_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    _clear_config_env(monkeypatch)
    (tmp_path / ".env").write_text(
        "LLM_API_KEY=sk-test-key\n"
        "LLM_BASE_URL=https://api.test.com\n"
        "LLM_MODEL=test-model\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = get_config()

    assert result == AppConfig(
        api_key="sk-test-key",
        base_url="https://api.test.com",
        model="test-model",
    )


def test_get_config_reports_missing_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    _clear_config_env(monkeypatch)
    (tmp_path / ".env").write_text(
        "LLM_BASE_URL=https://api.test.com\n"
        "LLM_MODEL=test-model\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ConfigError, match="LLM_API_KEY"):
        get_config()


def test_get_config_reports_missing_env_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    _clear_config_env(monkeypatch)
    project_root = tmp_path / "isolated_project"
    fake_app_dir = project_root / "app"
    fake_app_dir.mkdir(parents=True)
    fake_config_file = fake_app_dir / "config.py"
    fake_config_file.touch()
    empty_cwd = tmp_path / "empty_cwd"
    empty_cwd.mkdir()
    monkeypatch.setattr(config, "__file__", str(fake_config_file))
    monkeypatch.chdir(empty_cwd)

    with pytest.raises(ConfigError, match=r"\.env"):
        get_config()
