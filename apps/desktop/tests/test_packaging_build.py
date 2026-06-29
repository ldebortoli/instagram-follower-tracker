import importlib.util
from pathlib import Path

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
