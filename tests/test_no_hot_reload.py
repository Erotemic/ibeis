"""Regression checks for retired developer hot-reload infrastructure."""

import ast
from pathlib import Path


REPO_DPATH = Path(__file__).resolve().parents[1]
IBEIS_DPATH = REPO_DPATH / "ibeis"


def _parse(path):
    return ast.parse(path.read_text(), filename=str(path))


def test_package_initializers_do_not_define_recursive_reload_helpers():
    offenders = []
    for path in IBEIS_DPATH.rglob("__init__.py"):
        tree = _parse(path)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {
                "reload_subs",
                "reassign_submodule_attributes",
            }:
                offenders.append(f"{path.relative_to(REPO_DPATH)}:{node.lineno}:{node.name}")
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {"rrrr", "IMPORT_TUPLES"}:
                        offenders.append(
                            f"{path.relative_to(REPO_DPATH)}:{node.lineno}:{target.id}"
                        )
    assert not offenders, "legacy package reload helpers found: " + ", ".join(offenders)


def test_gui_does_not_expose_python_hot_reload():
    paths = [
        IBEIS_DPATH / "gui" / "guimenus.py",
        IBEIS_DPATH / "gui" / "guiback.py",
        IBEIS_DPATH / "viz" / "interact" / "interact_matches.py",
        IBEIS_DPATH / "viz" / "viz_graph.py",
    ]
    text = "\n".join(path.read_text() for path in paths)
    assert "Developer Reload" not in text
    assert "def dev_reload" not in text
    assert ".rrr()" not in text


def test_controller_has_no_hot_reload_lifecycle_hook():
    path = IBEIS_DPATH / "control" / "IBEISControl.py"
    tree = _parse(path)
    method_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "_on_reload" not in method_names


def test_ibeis_does_not_use_reloadable_class_decorator():
    offenders = []
    for path in IBEIS_DPATH.rglob("*.py"):
        tree = _parse(path)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Attribute) and decorator.attr == "reloadable_class":
                    offenders.append(
                        f"{path.relative_to(REPO_DPATH)}:{node.lineno}:{node.name}"
                    )
    assert not offenders, "reloadable_class decorators found: " + ", ".join(offenders)


if __name__ == "__main__":
    test_package_initializers_do_not_define_recursive_reload_helpers()
    test_gui_does_not_expose_python_hot_reload()
    test_controller_has_no_hot_reload_lifecycle_hook()
    test_ibeis_does_not_use_reloadable_class_decorator()
