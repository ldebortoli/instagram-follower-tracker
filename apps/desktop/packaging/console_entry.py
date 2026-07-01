import sqlite3
import sys
import tkinter

import keyring
from seguidores_desktop.cli import main


def packaging_self_test() -> int:
    sqlite3.connect(":memory:").close()
    tkinter.Tcl()
    keyring.get_keyring()
    print("packaging-self-test: ok")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--packaging-self-test"]:
        raise SystemExit(packaging_self_test())
    raise SystemExit(main())
