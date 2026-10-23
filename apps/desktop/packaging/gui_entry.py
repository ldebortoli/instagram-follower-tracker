import sqlite3
import sys
import tkinter

import keyring
from seguidores_desktop.gui import main


def packaging_self_test() -> int:
    sqlite3.connect(":memory:").close()
    tkinter.Tcl()
    keyring.get_keyring()
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--packaging-self-test"]:
        raise SystemExit(packaging_self_test())
    raise SystemExit(main())
