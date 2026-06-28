import sqlite3
import sys
import tkinter

import instaloader
import keyring

from seguidores.cli import main


def packaging_self_test() -> int:
    sqlite3.connect(":memory:").close()
    tkinter.Tcl()
    keyring.get_keyring()
    if not instaloader.__version__:
        return 1
    print("packaging-self-test: ok")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--packaging-self-test"]:
        raise SystemExit(packaging_self_test())
    raise SystemExit(main())
