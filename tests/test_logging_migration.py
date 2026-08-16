"""Static invariants for the Loguru workspace migration."""

import ast
from pathlib import Path


REPO_DPATH = Path(__file__).resolve().parents[1]
PACKAGE_ROOTS = [
    REPO_DPATH / 'ibeis',
    REPO_DPATH / 'tpl' / 'utool' / 'utool',
    REPO_DPATH / 'tpl' / 'dtool_ibeis' / 'dtool_ibeis',
    REPO_DPATH / 'tpl' / 'plottool_ibeis' / 'plottool_ibeis',
    REPO_DPATH / 'tpl' / 'guitool_ibeis' / 'guitool_ibeis',
    REPO_DPATH / 'tpl' / 'vtool_ibeis' / 'vtool_ibeis',
]
DEV_FILES = [
    REPO_DPATH / 'dev' / '_scripts' / '_timeits' / 'time_uuids.py',
    REPO_DPATH / 'dev' / 'unstable' / 'bayes.py',
    REPO_DPATH / 'dev' / 'unstable' / 'demobayes.py',
    REPO_DPATH / 'dev' / 'unstable' / 'devcases.py',
    REPO_DPATH / 'dev' / 'unstable' / 'distinctiveness_normalizer.py',
    REPO_DPATH / 'dev' / 'unstable' / 'iccv.py',
    REPO_DPATH / 'dev' / 'unstable' / 'multi_index.py',
    REPO_DPATH / 'dev' / 'unstable' / 'orig_graph_iden.py',
    REPO_DPATH / 'dev' / 'unstable' / 'pgm_ext.py',
    REPO_DPATH / 'dev' / 'unstable' / 'pgm_viz.py',
    REPO_DPATH / 'dev' / 'unstable' / 'precision_recall.py',
    REPO_DPATH / 'dev' / 'unstable' / 'scorenorm.py',
    REPO_DPATH / 'dev' / 'unstable' / 'script_bp_cut.py',
    REPO_DPATH / 'tpl' / 'utool' / 'dev' / '_broken' / 'util_distances.py',
    REPO_DPATH / 'tpl' / 'utool' / 'dev' / 'old' / 'tests' / '_oldtest_logging.py',
    REPO_DPATH / 'tpl' / 'vtool_ibeis' / 'dev' / 'unstable' / 'clustering.py',
]


def _python_files():
    for root in PACKAGE_ROOTS:
        if root.exists():
            yield from root.rglob('*.py')
    for path in DEV_FILES:
        if path.exists():
            yield path


def _parse(path):
    return ast.parse(path.read_text(), filename=str(path))


def _call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _decorator_name(node):
    if isinstance(node, ast.Call):
        node = node.func
    return _call_name(node)


def test_workspace_has_no_inject_calls():
    offenders = []
    for path in _python_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_name(node.func) in {'inject', 'inject2'}:
                offenders.append(f'{path.relative_to(REPO_DPATH)}:{node.lineno}')
    assert not offenders, 'legacy injection calls found: ' + ', '.join(offenders)


def test_workspace_has_no_injected_module_helper_calls():
    retired_helpers = {
        'make_module_print_func',
        'make_module_write_func',
        'make_module_profile_func',
        'make_module_reload_func',
        'inject_print_functions',
    }
    offenders = []
    for path in _python_files():
        # util_inject retains the legacy helper implementations as an isolated
        # compatibility module; current workspace code must not consume them.
        if path.name == 'util_inject.py':
            continue
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_name(node.func) in retired_helpers:
                offenders.append(
                    f'{path.relative_to(REPO_DPATH)}:{node.lineno}:{_call_name(node.func)}'
                )
    assert not offenders, 'legacy module helper calls found: ' + ', '.join(offenders)


def test_workspace_has_no_active_profile_decorators():
    offenders = []
    for path in _python_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for decorator in node.decorator_list:
                    if _decorator_name(decorator) == 'profile':
                        offenders.append(
                            f'{path.relative_to(REPO_DPATH)}:{node.lineno}:{node.name}'
                        )
    assert not offenders, 'legacy profile decorators found: ' + ', '.join(offenders)


def test_workspace_package_initializers_are_static():
    offenders = []
    for root in PACKAGE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob('__init__.py'):
            tree = _parse(path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _call_name(node.func) == 'dynamic_import':
                    offenders.append(
                        f'{path.relative_to(REPO_DPATH)}:{node.lineno}:dynamic_import'
                    )
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        if isinstance(target, ast.Name) and target.id == 'IMPORT_TUPLES':
                            offenders.append(
                                f'{path.relative_to(REPO_DPATH)}:{node.lineno}:IMPORT_TUPLES'
                            )
    assert not offenders, 'dynamic package initialization found: ' + ', '.join(offenders)


def test_line_profiler_is_not_loaded_by_utool_injection():
    path = REPO_DPATH / 'tpl' / 'utool' / 'utool' / 'util_inject.py'
    if not path.exists():
        return
    tree = _parse(path)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert 'line_profiler' not in imports


def test_utool_inject_module_does_not_configure_logging():
    path = REPO_DPATH / 'tpl' / 'utool' / 'utool' / 'util_inject.py'
    if not path.exists():
        return
    tree = _parse(path)
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_name(node.func) == 'start_logging':
            offenders.append(node.lineno)
    assert not offenders, 'utool import-time logging configuration remains: {!r}'.format(
        offenders
    )


def test_runtime_code_has_no_active_hot_reload_decorators():
    offenders = []
    for root in PACKAGE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob('*.py'):
            tree = _parse(path)
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                for decorator in node.decorator_list:
                    if _decorator_name(decorator) == 'reloadable_class':
                        offenders.append(
                            f'{path.relative_to(REPO_DPATH)}:{node.lineno}:{node.name}'
                        )
    assert not offenders, 'active hot-reload decorators found: ' + ', '.join(offenders)



def test_libraries_do_not_configure_loguru_at_import_time():
    config_methods = {'add', 'remove', 'configure', 'enable', 'disable'}
    offenders = []
    for root in PACKAGE_ROOTS[1:]:
        if not root.exists():
            continue
        for path in root.rglob('*.py'):
            tree = _parse(path)
            for node in tree.body:
                values = []
                if isinstance(node, ast.Expr):
                    values.append(node.value)
                elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                    values.append(node.value)
                for value in values:
                    if (
                        isinstance(value, ast.Call)
                        and isinstance(value.func, ast.Attribute)
                        and isinstance(value.func.value, ast.Name)
                        and value.func.value.id == 'logger'
                        and value.func.attr in config_methods
                    ):
                        offenders.append(
                            f'{path.relative_to(REPO_DPATH)}:{value.lineno}:logger.{value.func.attr}'
                        )
    assert not offenders, 'library import-time Loguru configuration found: ' + ', '.join(offenders)

def test_workspace_declares_loguru_dependency_where_needed():
    reqs = [
        REPO_DPATH / 'requirements' / 'runtime.txt',
        REPO_DPATH / 'tpl' / 'utool' / 'requirements' / 'runtime.txt',
        REPO_DPATH / 'tpl' / 'dtool_ibeis' / 'requirements' / 'runtime.txt',
        REPO_DPATH / 'tpl' / 'plottool_ibeis' / 'requirements' / 'runtime.txt',
        REPO_DPATH / 'tpl' / 'guitool_ibeis' / 'requirements' / 'runtime.txt',
        REPO_DPATH / 'tpl' / 'vtool_ibeis' / 'requirements' / 'tests.txt',
    ]
    for path in reqs:
        if path.exists():
            assert any(
                line.strip().startswith('loguru')
                for line in path.read_text().splitlines()
            ), str(path.relative_to(REPO_DPATH))
