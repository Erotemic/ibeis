#!/usr/bin/env bash
set -uo pipefail

# Run IBEIS and every checked-out tpl repository test suite in one environment.
# All suites are attempted by default, and the script returns nonzero if any
# suite failed. This gives a complete pre-publish failure summary instead of
# stopping at the first broken dependency.

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPORT_DIR=${IBEIS_TEST_REPORT_DIR:-"$REPO_ROOT/.full-suite-reports"}
FAIL_FAST=${IBEIS_TEST_FAIL_FAST:-0}
IBEIS_WORKDIR=${IBEIS_TEST_WORKDIR:-/tmp/ibeis-full-suite-workdir}

export MPLBACKEND=${MPLBACKEND:-Agg}
export QT_QPA_PLATFORM=${QT_QPA_PLATFORM:-offscreen}
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/tmp/xdg-runtime}
mkdir -p "$XDG_RUNTIME_DIR" "$REPORT_DIR"
chmod 700 "$XDG_RUNTIME_DIR" 2>/dev/null || true

# A persistent host-mounted report directory is useful across container runs,
# but reports for suites removed from the matrix would otherwise linger and
# look current. Only clear generated logs; leave unrelated user files alone.
find "$REPORT_DIR" -maxdepth 1 -type f -name '*.log' -delete

# Dependency-oriented order makes failures easier to interpret. IBEIS itself is
# last so its result reflects the exact local ecosystem that was just tested.
SUITES=(
    "utool|tpl/utool"
    "pyflann_ibeis|tpl/pyflann_ibeis"
    "pyhesaff|tpl/pyhesaff"
    "vtool_ibeis_ext|tpl/vtool_ibeis_ext"
    "vtool_ibeis|tpl/vtool_ibeis"
    "guitool_ibeis|tpl/guitool_ibeis"
    "dtool_ibeis|tpl/dtool_ibeis"
    "plottool_ibeis|tpl/plottool_ibeis"
    "ibeis|."
)

prepare_ibeis_suite() {
    # Mirror the database preparation performed by the regular IBEIS CI job.
    # A fresh workdir keeps this full-stack run independent of developer caches
    # and ensures doctests can resolve testdb1 / PZ_MTEST / the other fixtures
    # they expect.
    rm -rf "$IBEIS_WORKDIR"
    mkdir -p "$IBEIS_WORKDIR"
    (
        cd "$REPO_ROOT"
        python -m ibeis --set-workdir="$IBEIS_WORKDIR" --nogui
        python -m ibeis --resetdbs
        # --resetdbs intentionally prepares only the small CI databases. Two
        # active H.O.T.S. tests use PZ_MTEST directly, so include that standard
        # fixture in the full ecosystem environment as well.
        python - <<'PY'
import ibeis
ibeis.ensure_pz_mtest()
PY
    )
}

run_suite() {
    local name=$1
    local relpath=$2
    local suite_dir="$REPO_ROOT/$relpath"
    local logfile="$REPORT_DIR/${name}.log"

    if [[ ! -d "$suite_dir" ]]; then
        echo "[full-suite] ERROR: missing suite directory: $suite_dir" | tee "$logfile"
        return 2
    fi

    echo
    echo "================================================================================"
    echo "[full-suite] START $name ($relpath)"
    echo "================================================================================"

    if [[ "$name" == "ibeis" ]]; then
        echo "[full-suite] preparing IBEIS test databases in $IBEIS_WORKDIR"
        if ! prepare_ibeis_suite 2>&1 | tee "$REPORT_DIR/ibeis-prepare.log"; then
            echo "[full-suite] FAIL ibeis database preparation"
            return 3
        fi
    fi

    local -a command
    case "$name" in
        pyhesaff|vtool_ibeis_ext)
            # Their wheel-oriented run_tests.py scripts intentionally remove the
            # source checkout from module discovery and then look for a separate
            # installed package. In this image the package is deliberately
            # editable, so run pytest directly against both source and tests.
            command=(
                python -m pytest
                --cov-config pyproject.toml
                --cov-report html
                --cov-report term
                --cov-report xml
                --cov="$name"
                "$name"
                tests
            )
            ;;
        *)
            if [[ -f "$suite_dir/run_tests.py" ]]; then
                command=(python run_tests.py)
            else
                # Fallback for future tpl repositories.
                command=(python -m pytest)
            fi
            ;;
    esac

    # A virtual framebuffer is more compatible with legacy Qt tests than
    # relying only on QT_QPA_PLATFORM=offscreen. Use it when the image provides
    # xvfb-run, while keeping the script usable directly on developer machines.
    if command -v xvfb-run >/dev/null 2>&1; then
        command=(xvfb-run -a --server-args=-screen\ 0\ 1280x1024x24 "${command[@]}")
    fi

    echo "[full-suite] command: ${command[*]}"
    echo "[full-suite] log: $logfile"

    (
        cd "$suite_dir"
        "${command[@]}"
    ) 2>&1 | tee "$logfile"
    local rc=${PIPESTATUS[0]}

    if [[ $rc -eq 0 ]]; then
        echo "[full-suite] PASS $name"
    else
        echo "[full-suite] FAIL $name (exit=$rc)"
    fi
    return "$rc"
}

declare -a PASSED=()
declare -a FAILED=()

for entry in "${SUITES[@]}"; do
    IFS='|' read -r name relpath <<< "$entry"
    if run_suite "$name" "$relpath"; then
        PASSED+=("$name")
    else
        rc=$?
        FAILED+=("$name:$rc")
        if [[ "$FAIL_FAST" == "1" ]]; then
            break
        fi
    fi
done

echo
echo "================================================================================"
echo "[full-suite] SUMMARY"
echo "================================================================================"
printf '[full-suite] passed (%d):' "${#PASSED[@]}"
if [[ ${#PASSED[@]} -gt 0 ]]; then
    printf ' %s' "${PASSED[@]}"
fi
echo

if [[ ${#FAILED[@]} -gt 0 ]]; then
    printf '[full-suite] failed (%d):' "${#FAILED[@]}"
    printf ' %s' "${FAILED[@]}"
    echo
    echo "[full-suite] logs: $REPORT_DIR"
    exit 1
else
    echo '[full-suite] failed (0): none'
    echo "[full-suite] logs: $REPORT_DIR"
    exit 0
fi
