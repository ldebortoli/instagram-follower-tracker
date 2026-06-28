import tkinter as tk

import pytest

from seguidores.gui import ALL_ACCOUNTS, SeguidoresApp
from seguidores.paths import AppPaths


@pytest.fixture
def gui(tmp_path):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("El runner no tiene una sesión gráfica.")
    root.withdraw()
    app = SeguidoresApp(root, AppPaths(tmp_path))
    root.update_idletasks()
    yield app
    root.destroy()


def test_gui_builds_all_configuration_tabs_without_creating_config(gui):
    assert gui.notebook.index("end") == 4
    assert gui.run_account.get() == ALL_ACCOUNTS
    assert not gui.paths.config.exists()


def test_gui_account_form_builds_valid_account(gui):
    gui.account_name.set("personal")
    gui.instagram_username.set("@Owner.Name")
    gui.login_username.set("")

    account = gui._account_from_form()

    assert account.name == "personal"
    assert account.username == "owner.name"
    assert account.login_username == "owner.name"
