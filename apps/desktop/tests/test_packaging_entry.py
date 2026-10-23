import sys
import zipfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


def test_direct_packaging_entry_runs_only_fake_builder_and_smoke_commands(tmp_path, monkeypatch):
    """Exercise the unchanged script with synthetic resource paths and a fake PyInstaller."""
    source = Path(__file__).parents[1] / "packaging/build.py"
    fake_location = tmp_path / "apps/desktop/packaging/build.py"
    fake_location.parent.mkdir(parents=True)
    (fake_location.parent / "README-DISTRIBUTION.md").write_text("synthetic readme")
    (tmp_path / "LICENSE").write_text("synthetic license")
    package, builder = ModuleType("PyInstaller"), ModuleType("PyInstaller.__main__")
    builds = []

    def fake_build(arguments):
        builds.append(arguments)
        output = Path(arguments[arguments.index("--distpath") + 1])
        output.mkdir(parents=True)
        (output / "seguidores-gui.exe").write_bytes(b"synthetic fixture; not an executable")

    builder.run = fake_build
    package.__main__ = builder
    monkeypatch.setitem(sys.modules, "PyInstaller", package)
    monkeypatch.setitem(sys.modules, "PyInstaller.__main__", builder)
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr("platform.machine", lambda: "AMD64")
    smoke = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr("subprocess.run", smoke)
    with pytest.raises(SystemExit) as stopped:
        exec(
            compile(source.read_bytes(), str(source), "exec"),
            {"__name__": "__main__", "__file__": str(fake_location)},
        )
    assert stopped.value.code == 0
    assert len(builds) == 1 and builds[0][0] == str(fake_location.parent / "gui_entry.py")
    assert [call.args[0][-1] for call in smoke.call_args_list] == [
        "--version",
        "--packaging-self-test",
    ]
    archives = list((tmp_path / "release").glob("*.zip"))
    assert len(archives) == 1
    with zipfile.ZipFile(archives[0]) as archive:
        files = {Path(name).name for name in archive.namelist() if not name.endswith("/")}
    assert files == {"seguidores-gui.exe", "LEEME.md", "LICENSE"}
    assert archives[0].with_suffix(".zip.sha256").is_file()
