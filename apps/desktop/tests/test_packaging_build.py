import importlib.util
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def _build_module():
    path = Path(__file__).parents[1] / "packaging" / "build.py"
    spec = importlib.util.spec_from_file_location("seguidores_packaging_build", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_packaging_paths_point_to_monorepo_layout():
    module = _build_module()
    repository = Path(__file__).resolve().parents[3]

    assert repository == module.ROOT
    assert repository / "apps" / "desktop" == module.DESKTOP_ROOT
    assert module.PACKAGE_README.is_file()


def test_reset_outputs_keeps_previous_releases(tmp_path, monkeypatch):
    module = _build_module()
    build = tmp_path / "build" / "standalone"
    dist = tmp_path / "dist" / "standalone"
    release = tmp_path / "release"
    for directory in (build, dist, release):
        directory.mkdir(parents=True)
        (directory / "existing.txt").write_text("keep", encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "BUILD", build)
    monkeypatch.setattr(module, "DIST", dist)
    monkeypatch.setattr(module, "RELEASE", release)

    module._reset_outputs()

    assert not build.exists()
    assert not dist.exists()
    assert (release / "existing.txt").read_text(encoding="utf-8") == "keep"


def test_reset_outputs_explains_locked_executable(tmp_path, monkeypatch):
    module = _build_module()
    build = tmp_path / "build" / "standalone"
    build.mkdir(parents=True)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "BUILD", build)
    monkeypatch.setattr(module, "DIST", tmp_path / "dist" / "standalone")
    monkeypatch.setattr(
        module.shutil,
        "rmtree",
        lambda _path: (_ for _ in ()).throw(PermissionError("locked")),
    )

    with pytest.raises(RuntimeError, match="Cerrá cualquier ejecutable"):
        module._reset_outputs()


@pytest.mark.parametrize("system", ["Windows", "Darwin", "Linux"])
def test_smoke_test_runs_only_gui_checks_in_isolated_home(system, tmp_path, monkeypatch):
    module = _build_module()
    monkeypatch.setattr(module, "BUILD", tmp_path / "build")
    monkeypatch.setattr(module.platform, "system", lambda: system)
    gui = tmp_path / ("Seguidores.app" if system == "Darwin" else "seguidores-gui")
    commands = []

    def run(command, **options):
        commands.append((command, options))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.subprocess, "run", run)
    module._smoke_test(gui)

    executable = gui / "Contents/MacOS/Seguidores" if system == "Darwin" else gui
    assert [command for command, _options in commands] == [
        [str(executable), "--version"],
        [str(executable), "--packaging-self-test"],
    ]
    assert all(options["check"] for _command, options in commands)
    assert all(
        options["env"]["SEGUIDORES_HOME"] == str(tmp_path / "build/smoke-home")
        for _command, options in commands
    )


@pytest.mark.parametrize("failed_flag", ["--version", "--packaging-self-test"])
def test_smoke_test_stops_on_failed_gui_check(failed_flag, tmp_path, monkeypatch):
    module = _build_module()
    commands = []
    monkeypatch.setattr(module.platform, "system", lambda: "Windows")

    def run(command, **_options):
        commands.append(command)
        if command[-1] == failed_flag:
            raise subprocess.CalledProcessError(3, command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        module._smoke_test(tmp_path / "seguidores-gui.exe")

    assert commands[-1][-1] == failed_flag


@pytest.mark.parametrize(
    ("system", "name", "onefile"),
    [("Windows", "seguidores-gui", True), ("Darwin", "Seguidores", False),
     ("Linux", "seguidores-gui", True)],
)
def test_build_pipeline_builds_and_packages_only_gui(
    system, name, onefile, tmp_path, monkeypatch, capsys
):
    module = _build_module()
    builds = []
    checked = []
    monkeypatch.setattr(module.platform, "system", lambda: system)
    monkeypatch.setattr(module.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(module, "_reset_outputs", lambda: None)

    def build(entry, title, **options):
        builds.append((entry, title, options))

    monkeypatch.setattr(module, "_build_entry", build)
    monkeypatch.setattr(module, "_smoke_test", checked.append)
    archive = tmp_path / "package.zip"
    archive.write_bytes(b"synthetic package")

    def package(os_name, architecture, gui):
        assert os_name == system and architecture == "x86_64"
        assert gui == module._gui_path(name, system)
        return archive

    monkeypatch.setattr(module, "_package", package)

    assert module.main() == 0
    assert builds == [
        (module.DESKTOP_ROOT / "packaging/gui_entry.py", name,
         {"windowed": True, "onefile": onefile})
    ]
    assert checked == [module._gui_path(name, system)]
    assert archive.with_name("package.zip.sha256").is_file()
    assert "Paquete:" in capsys.readouterr().out


@pytest.mark.parametrize("system", ["Windows", "Linux"])
def test_archive_contains_gui_license_and_instructions_only(system, tmp_path, monkeypatch):
    module = _build_module()
    readme = tmp_path / "README.md"
    readme.write_text("synthetic instructions", encoding="utf-8")
    (tmp_path / "LICENSE").write_text("synthetic license", encoding="utf-8")
    gui = tmp_path / ("seguidores-gui.exe" if system == "Windows" else "seguidores-gui")
    gui.write_bytes(b"synthetic executable fixture")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "BUILD", tmp_path / "build")
    monkeypatch.setattr(module, "RELEASE", tmp_path / "release")
    monkeypatch.setattr(module, "PACKAGE_README", readme)

    archive = module._package(system, "x86_64", gui)

    if system == "Windows":
        with zipfile.ZipFile(archive) as package:
            files = [entry.filename for entry in package.infolist() if not entry.is_dir()]
    else:
        with tarfile.open(archive) as package:
            files = [entry.name for entry in package.getmembers() if entry.isfile()]
    assert {Path(name).name for name in files} == {gui.name, "LEEME.md", "LICENSE"}


def test_macos_archive_keeps_app_bundle_and_mocks_platform_tools(tmp_path, monkeypatch):
    module = _build_module()
    gui = tmp_path / "Seguidores.app"
    (gui / "Contents").mkdir(parents=True)
    (gui / "Contents/fixture").write_bytes(b"synthetic bundle")
    readme = tmp_path / "README.md"
    readme.write_text("instructions", encoding="utf-8")
    (tmp_path / "LICENSE").write_text("license", encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "BUILD", tmp_path / "build")
    monkeypatch.setattr(module, "RELEASE", tmp_path / "release")
    monkeypatch.setattr(module, "PACKAGE_README", readme)
    commands = []
    monkeypatch.setattr(
        module.subprocess, "run", lambda command, **_options: commands.append(command)
    )

    archive = module._package("Darwin", "arm64", gui)

    assert archive.name == f"Seguidores-{module.__version__}-macOS-arm64.zip"
    stage = module.BUILD / "package" / archive.stem
    assert (stage / "Seguidores.app/Contents/fixture").read_bytes() == b"synthetic bundle"
    assert [command[0] for command in commands] == ["codesign", "ditto"]
    assert commands[0][-1] == str(stage / "Seguidores.app")
    assert commands[1][-1] == str(archive)


@pytest.mark.parametrize(
    ("system", "windowed", "onefile"),
    [("Windows", True, True), ("Darwin", True, False), ("Linux", False, True)],
)
def test_pyinstaller_arguments_use_gui_entry_without_running_builder(
    system, windowed, onefile, tmp_path, monkeypatch
):
    module = _build_module()
    package = ModuleType("PyInstaller")
    builder = ModuleType("PyInstaller.__main__")
    arguments = []
    builder.run = arguments.extend
    package.__main__ = builder
    monkeypatch.setitem(sys.modules, "PyInstaller", package)
    monkeypatch.setitem(sys.modules, "PyInstaller.__main__", builder)
    monkeypatch.setattr(module.platform, "system", lambda: system)
    monkeypatch.setattr(module, "BUILD", tmp_path / "build")
    monkeypatch.setattr(module, "DIST", tmp_path / "dist")
    entry = module.DESKTOP_ROOT / "packaging/gui_entry.py"

    module._build_entry(entry, "gui-fixture", windowed=windowed, onefile=onefile)

    assert arguments[0] == str(entry)
    assert ("--windowed" in arguments) == windowed
    assert ("--onefile" in arguments) == onefile
    assert ("--onedir" in arguments) != onefile
    assert ("--osx-bundle-identifier" in arguments) == (system == "Darwin" and windowed)


def test_reset_outputs_rejects_paths_outside_project(tmp_path, monkeypatch):
    module = _build_module()
    monkeypatch.setattr(module, "ROOT", tmp_path / "project")
    monkeypatch.setattr(module, "BUILD", tmp_path / "outside")

    with pytest.raises(RuntimeError, match="Ruta de build insegura"):
        module._reset_outputs()


@pytest.mark.parametrize(
    ("machine", "expected"),
    [("AMD64", "x86_64"), ("x64", "x86_64"), ("arm64", "arm64"),
     ("aarch64", "arm64"), ("Other CPU", "other-cpu")],
)
def test_architecture_names_are_portable(machine, expected):
    assert _build_module()._architecture(machine) == expected
