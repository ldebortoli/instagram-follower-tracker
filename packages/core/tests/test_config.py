import json

import pytest
from seguidores.config import AccountConfig, ConfigError, default_config, load_config, save_config
from seguidores.paths import AppPaths


def test_config_roundtrip(tmp_path):
    paths = AppPaths(tmp_path)
    config = default_config()
    config.accounts.append(AccountConfig("personal", "Owner.Name", "Login.Name"))
    config.schedule.time = "07:30"

    save_config(paths, config)
    loaded = load_config(paths)

    assert loaded.accounts[0].username == "owner.name"
    assert loaded.accounts[0].login_username == "login.name"
    assert loaded.schedule.time == "07:30"
    assert json.loads(paths.config.read_text(encoding="utf-8"))["schema_version"] == 1


@pytest.mark.parametrize("value", ["7:30", "24:00", "09:60", "nueve", "09"])
def test_invalid_schedule_time_is_rejected(tmp_path, value):
    config = default_config()
    config.schedule.time = value

    with pytest.raises(ConfigError):
        save_config(AppPaths(tmp_path), config)


def test_duplicate_account_names_are_case_insensitive(tmp_path):
    config = default_config()
    config.accounts = [
        AccountConfig("Personal", "one", "one"),
        AccountConfig("personal", "two", "two"),
    ]

    with pytest.raises(ConfigError, match="repetido"):
        save_config(AppPaths(tmp_path), config)
