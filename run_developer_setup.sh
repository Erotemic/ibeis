#!/usr/bin/env bash
set -euo pipefail

# Developer setup: editable ("develop mode") install of ibeis and its
# ecosystem submodules into a virtualenv, including test dependencies,
# so pytest runs against the whole in-source stack.
#
# Usage:
#   ./run_developer_setup.sh                    # pure-python repos editable,
#                                               # compiled repos from PyPI wheels
#   IBEIS_DEV_BINARY=1 ./run_developer_setup.sh # ALSO build the compiled repos
#                                               # from source (needs a C++
#                                               # toolchain; slow)
#
# If no virtualenv is active, ./.venv is created (with uv when available)
# and used.

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$REPO_ROOT"

# --- virtualenv ---
if [ -z "${VIRTUAL_ENV:-}" ]; then
    if [ ! -e ".venv/bin/activate" ]; then
        echo "[setup] creating .venv"
        if command -v uv >/dev/null 2>&1; then
            uv venv .venv
        else
            python3 -m venv .venv
        fi
    fi
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi
echo "[setup] python = $(command -v python)"

# uv makes installs much faster when present; fall back to pip.
if command -v uv >/dev/null 2>&1; then
    PIP_INSTALL=(uv pip install)
else
    python -m pip install -U pip
    PIP_INSTALL=(python -m pip install)
fi

# --- submodules ---
if [ -e .git ] && [ ! -e tpl/utool/setup.py ]; then
    echo "[setup] initializing tpl/ submodules"
    git submodule update --init --recursive
fi

# Pure-python ecosystem repos: installed editable so changes to them are
# picked up live alongside ibeis.
PUREPY_PKGS=(
    tpl/utool
    tpl/vtool_ibeis
    tpl/dtool_ibeis
    tpl/plottool_ibeis
    tpl/guitool_ibeis
)

# Compiled repos: default to the PyPI wheels pulled in as ibeis deps.
# Editable source builds need cmake/ninja/C++ (and OpenCV for pyhesaff);
# opt in with IBEIS_DEV_BINARY=1.
BINARY_PKGS=(
    tpl/pyhesaff
    tpl/pyflann_ibeis
    tpl/vtool_ibeis_ext
)

# 1) ibeis itself (editable) plus runtime and test deps. This also pulls
#    binary wheels for the compiled ecosystem packages.
echo "[setup] installing ibeis (editable) + runtime/test deps"
"${PIP_INSTALL[@]}" -e ".[headless,tests]"

# 2) Swap the pure-python ecosystem packages for editable checkouts.
#    Submodule versions satisfy the pins in requirements/runtime.txt, so
#    these replace the PyPI copies in place.
EDITABLE_ARGS=()
for pkg in "${PUREPY_PKGS[@]}"; do
    if [ ! -e "$pkg/setup.py" ] && [ ! -e "$pkg/pyproject.toml" ]; then
        echo "[setup] WARNING: skipping missing submodule $pkg (git submodule update --init?)"
        continue
    fi
    EDITABLE_ARGS+=(-e "./$pkg")
done
if [ "${#EDITABLE_ARGS[@]}" -gt 0 ]; then
    echo "[setup] editable install: ${EDITABLE_ARGS[*]}"
    "${PIP_INSTALL[@]}" "${EDITABLE_ARGS[@]}"
fi

# 3) Optionally build the compiled repos from source in editable mode.
if [ "${IBEIS_DEV_BINARY:-0}" = "1" ]; then
    for pkg in "${BINARY_PKGS[@]}"; do
        if [ ! -e "$pkg/setup.py" ] && [ ! -e "$pkg/pyproject.toml" ]; then
            echo "[setup] WARNING: skipping missing submodule $pkg"
            continue
        fi
        echo "[setup] source build (editable): $pkg"
        "${PIP_INSTALL[@]}" -e "./$pkg"
    done
fi

# --- verify ---
echo "[setup] verifying editable installs"
python - <<'EOF'
import sys
mods = [
    'ibeis', 'utool', 'vtool_ibeis', 'dtool_ibeis', 'plottool_ibeis',
    'guitool_ibeis', 'pyhesaff', 'pyflann_ibeis',
    'vtool_ibeis_ext',
]
bad = []
for name in mods:
    try:
        mod = __import__(name)
    except Exception as ex:
        bad.append((name, repr(ex)))
        continue
    print(f'  {name:<18} {getattr(mod, "__version__", "?"):<10} {mod.__file__}')
if bad:
    for name, err in bad:
        print(f'  {name:<18} IMPORT FAILED: {err}')
    sys.exit(1)
print('[setup] OK: all ecosystem packages import')
EOF

echo "[setup] done. Run tests with: python run_tests.py  (or: pytest ibeis tests)"
