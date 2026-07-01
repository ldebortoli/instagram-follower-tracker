import json

import pytest
from seguidores.config import AccountConfig, ConfigError, default_config, load_config, save_config
from seguidores.paths import AppPaths


def test_config_roundtrip(tmp_path):
    paths = AppPaths(tmp_path)
    config = default_config()
    config.accounts.append(AccountConfig("personal", "Owner.Name"))

    save_config(paths, config)
    loaded = load_config(paths)

    assert loaded.accounts[0].username == "owner.name"
    assert json.loads(paths.config.read_text(encoding="utf-8"))["schema_version"] == 2


def test_version_one_config_is_migrated_without_login_or_schedule(tmp_path):
    paths = AppPaths(tmp_path)
    paths.config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "accounts": [
                    {
                        "name": "personal",
                        "username": "Owner",
                        "login_username": "Login",
                        "enabled": True,
                    }
                ],
                "notifications": {"popup": False},
                "schedule": {"enabled": True, "time": "09:00", "backend": "windows"},
            }
        ),
        encoding="utf-8",
    )

    config = load_config(paths)
    save_config(paths, config)
    raw = json.loads(paths.config.read_text(encoding="utf-8"))

    assert config.accounts == [AccountConfig("personal", "owner")]
    assert "schedule" not in raw
    assert "login_username" not in raw["accounts"][0]


def test_duplicate_account_names_are_case_insensitive(tmp_path):
    config = default_config()
    config.accounts = [AccountConfig("Personal", "one"), AccountConfig("personal", "two")]

    with pytest.raises(ConfigError, match="repetido"):
        save_config(AppPaths(tmp_path), config)
