from seguidores.cli import main, parser


def test_setup_uses_gui_by_default_and_keeps_terminal_option():
    graphical = parser().parse_args(["setup"])
    terminal = parser().parse_args(["setup", "--terminal"])
    gui = parser().parse_args(["gui"])

    assert not graphical.terminal
    assert terminal.terminal
    assert gui.command == "gui"


def test_session_id_auth_is_interactive_and_not_a_command_argument():
    arguments = parser().parse_args(["auth", "import-sessionid", "personal"])

    assert arguments.auth_command == "import-sessionid"
    assert arguments.account == "personal"
    assert not hasattr(arguments, "sessionid")


def test_init_and_empty_account_list(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SEGUIDORES_HOME", str(tmp_path))

    assert main(["init"]) == 0
    assert main(["account", "list"]) == 0

    output = capsys.readouterr().out
    assert "Configuración creada" in output
    assert "No hay cuentas configuradas" in output


def test_account_add_and_config_show(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SEGUIDORES_HOME", str(tmp_path))
    main(["init"])

    assert main(["account", "add", "personal", "--username", "My.Owner"]) == 0
    assert main(["config", "show"]) == 0

    output = capsys.readouterr().out
    assert '"username": "my.owner"' in output
    assert '"login_username": "my.owner"' in output
