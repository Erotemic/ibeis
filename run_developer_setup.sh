#!/bin/bash

#!/usr/bin/env bash
set -euo pipefail

# Install tpl repos in editable mode.
# Prefer each repo's own developer setup script because some of the compiled
# packages need custom build steps before / during editable install.
DEV_PKGS=(
    tpl/utool
    tpl/pyhesaff
    tpl/pyflann_ibeis
    tpl/vtool_ibeis
    tpl/dtool_ibeis
    tpl/plottool_ibeis
    tpl/guitool_ibeis
    tpl/futures_actors
    tpl/vtool_ibeis_ext
)

for pkg in "${DEV_PKGS[@]}"; do
    if [ ! -d "$pkg" ]; then
        echo "[run_developer_setup] skipping missing $pkg"
        continue
    fi

    echo "[run_developer_setup] editable install for $pkg"
    python -m pip install -e "$pkg"
done

# TODO: fixme, for pyflan ibeis we currently need to
# python setup.py build_ext --inplace
# we should be able to fix this.
# looks like vtool_ibeis_ext (non-rust branch) also needs this.

# Install top-level non-editable deps for ibeis itself
python -m pip install -r requirements.txt

# Install ibeis itself in develop / editable mode
#python setup.py develop
python -m pip install -e .


## Install dependency packages
#pip install -r requirements.txt

## new pep makes this not always work
## pip install -e .
#python setup.py develop
