import json

from seguidores_desktop.cli import main, parser


def test_setup_uses_gui_by_default_and_keeps_terminal_option():
    graphical = parser().parse_args(["setup"])
    terminal = parser().parse_args(["setup", "--terminal"])
    gui = parser().parse_args(["gui"])

    assert not graphical.terminal
    assert terminal.terminal
    assert gui.command == "gui"


def test_import_json_accepts_multiple_follower_files():
    arguments = parser().parse_args(
        [
            "import-json",
            "personal",
            "--followers",
            "followers_1.json",
            "followers_2.json",
            "--following",
            "following.json",
        ]
    )

    assert len(arguments.followers) == 2
    assert len(arguments.following) == 1


def test_init_and_empty_account_list(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SEGUIDORES_HOME", str(tmp_path))

    assert main(["init"]) == 0
    assert main(["account", "list"]) == 0

    output = capsys.readouterr().out
    assert "Configuración creada" in output
    assert "No hay perfiles configurados" in output


def test_import_json_from_console(tmp_path, monkeypatch, capsys):
    followers = tmp_path / "followers_1.json"
    following = tmp_path / "following.json"
    followers.write_text(json.dumps([{"string_list_data": [{"value": "alice"}]}]), encoding="utf-8")
    following.write_text(
        json.dumps({"relationships_following": [{"title": "bob"}]}), encoding="utf-8"
    )
    monkeypatch.setenv("SEGUIDORES_HOME", str(tmp_path / "home"))
    main(["init"])
    main(["account", "add", "personal", "--username", "owner"])

    result = main(
        [
            "import-json",
            "personal",
            "--followers",
            str(followers),
            "--following",
            str(following),
        ]
    )

    assert result == 0
    assert "Seguidores: 1" in capsys.readouterr().out
