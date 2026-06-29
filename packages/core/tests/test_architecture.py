import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def imported_roots(source_root: Path) -> set[str]:
    roots: set[str] = set()
    for source_file in source_root.rglob("*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".", maxsplit=1)[0])
    return roots


def test_core_does_not_depend_on_applications():
    imports = imported_roots(ROOT / "packages" / "core" / "src")
    assert "seguidores_desktop" not in imports
    assert "jo_bot" not in imports


def test_applications_do_not_depend_on_each_other():
    desktop_imports = imported_roots(ROOT / "apps" / "desktop" / "src")
    bot_imports = imported_roots(ROOT / "apps" / "jo-bot" / "src")

    assert "jo_bot" not in desktop_imports
    assert "seguidores_desktop" not in bot_imports
