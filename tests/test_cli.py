from seguidores.cli import main


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
