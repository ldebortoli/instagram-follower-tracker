from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
from pathlib import Path

from seguidores import __version__

DESKTOP_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[3]
BUILD = ROOT / "build" / "standalone"
DIST = ROOT / "dist" / "standalone"
RELEASE = ROOT / "release"
PACKAGE_README = DESKTOP_ROOT / "packaging" / "README-DISTRIBUTION.md"


def main() -> int:
    system = platform.system()
    architecture = _architecture(platform.machine())
    _reset_outputs()

    console_name = "seguidores-cli" if system == "Darwin" else "seguidores"
    gui_name = "Seguidores" if system == "Darwin" else "seguidores-gui"
    _build_entry(DESKTOP_ROOT / "packaging" / "console_entry.py", console_name)
    _build_entry(
        DESKTOP_ROOT / "packaging" / "gui_entry.py",
        gui_name,
        windowed=True,
        onefile=system != "Darwin",
    )

    console = _console_path(console_name, system)
    gui = _gui_path(gui_name, system)
    _smoke_test(console, gui)
    archive = _package(system, architecture, console, gui)
    checksum = _write_checksum(archive)
    print(f"Paquete: {archive}")
    print(f"SHA-256: {checksum}")
    return 0


def _build_entry(
    entry: Path,
    name: str,
    *,
    windowed: bool = False,
    onefile: bool = True,
) -> None:
    import PyInstaller.__main__

    arguments = [
        str(entry),
        "--noconfirm",
        "--clean",
        "--noupx",
        "--name",
        name,
        "--paths",
        str(ROOT / "packages" / "core" / "src"),
        "--paths",
        str(DESKTOP_ROOT / "src"),
        "--distpath",
        str(DIST),
        "--workpath",
        str(BUILD / name),
        "--specpath",
        str(BUILD / "spec"),
    ]
    arguments.append("--onefile" if onefile else "--onedir")
    if windowed:
        arguments.append("--windowed")
    if platform.system() == "Darwin" and windowed:
        arguments.extend(["--osx-bundle-identifier", "com.ldebortoli.seguidores"])
    PyInstaller.__main__.run(arguments)


def _console_path(name: str, system: str) -> Path:
    suffix = ".exe" if system == "Windows" else ""
    return DIST / f"{name}{suffix}"


def _gui_path(name: str, system: str) -> Path:
    if system == "Darwin":
        return DIST / f"{name}.app"
    suffix = ".exe" if system == "Windows" else ""
    return DIST / f"{name}{suffix}"


def _smoke_test(console: Path, gui: Path) -> None:
    environment = {**os.environ, "SEGUIDORES_HOME": str(BUILD / "smoke-home")}
    console_result = subprocess.run(
        [str(console), "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
        env=environment,
    )
    if __version__ not in console_result.stdout:
        raise RuntimeError("El ejecutable de consola no informó la versión esperada.")
    self_test = subprocess.run(
        [str(console), "--packaging-self-test"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
        env=environment,
    )
    if "packaging-self-test: ok" not in self_test.stdout:
        raise RuntimeError("El ejecutable no superó la prueba de dependencias incluidas.")

    gui_executable = gui
    if platform.system() == "Darwin":
        gui_executable = gui / "Contents" / "MacOS" / gui.stem
    subprocess.run(
        [str(gui_executable), "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
        env=environment,
    )


def _package(system: str, architecture: str, console: Path, gui: Path) -> Path:
    os_name = {"Windows": "Windows", "Darwin": "macOS", "Linux": "Linux"}.get(system, system)
    package_name = f"Seguidores-{__version__}-{os_name}-{architecture}"
    stage = BUILD / "package" / package_name
    stage.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PACKAGE_README, stage / "LEEME.md")
    shutil.copy2(ROOT / "LICENSE", stage / "LICENSE")
    shutil.copy2(console, stage / console.name)
    if gui.is_dir():
        shutil.copytree(gui, stage / gui.name, symlinks=True)
        subprocess.run(
            ["codesign", "--force", "--deep", "--sign", "-", str(stage / gui.name)],
            check=True,
            timeout=120,
        )
    else:
        shutil.copy2(gui, stage / gui.name)

    RELEASE.mkdir(parents=True, exist_ok=True)
    archive_base = RELEASE / package_name
    if system == "Darwin":
        archive = archive_base.parent / f"{archive_base.name}.zip"
        subprocess.run(
            [
                "ditto",
                "-c",
                "-k",
                "--sequesterRsrc",
                "--keepParent",
                str(stage),
                str(archive),
            ],
            check=True,
            timeout=300,
        )
        return archive
    if system == "Windows":
        return Path(
            shutil.make_archive(
                str(archive_base), "zip", root_dir=stage.parent, base_dir=stage.name
            )
        )
    return Path(
        shutil.make_archive(str(archive_base), "gztar", root_dir=stage.parent, base_dir=stage.name)
    )


def _write_checksum(archive: Path) -> Path:
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    checksum = archive.with_name(archive.name + ".sha256")
    checksum.write_text(f"{digest.hexdigest()}  {archive.name}\n", encoding="utf-8")
    return checksum


def _reset_outputs() -> None:
    # RELEASE contains packages the user may currently be testing. Removing the
    # whole directory fails on Windows when an older executable is open and is
    # unnecessary: the current archive and checksum are overwritten later.
    for path in (BUILD, DIST):
        resolved = path.resolve()
        if ROOT.resolve() not in resolved.parents:
            raise RuntimeError(f"Ruta de build insegura: {resolved}")
        if resolved.exists():
            try:
                shutil.rmtree(resolved)
            except PermissionError as exc:
                raise RuntimeError(
                    f"No se pudo limpiar {resolved}. Cerrá cualquier ejecutable de Seguidores "
                    "abierto desde las carpetas build o dist y volvé a ejecutar el script."
                ) from exc


def _architecture(machine: str) -> str:
    normalized = machine.lower()
    if normalized in {"amd64", "x86_64", "x64"}:
        return "x86_64"
    if normalized in {"arm64", "aarch64"}:
        return "arm64"
    return normalized.replace(" ", "-")


if __name__ == "__main__":
    raise SystemExit(main())
