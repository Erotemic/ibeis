#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
ROOT="${IBEIS_REPO:-$DEFAULT_ROOT}"
SHOW_ALL_SUBMODULES="${SHOW_ALL_SUBMODULES:-0}"
STRICT="${STRICT:-0}"

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

read_version() {
    local path="$1"
    [[ -f "$path" ]] || return 1
    python - "$path" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text()
match = re.search(
    r"(?m)^\s*__version__\s*=\s*(['\"])([^'\"]+)\1\s*(?:#.*)?$",
    text,
)
if not match:
    raise SystemExit(1)
print(match.group(2))
PY
}

branch_name() {
    local repo="$1"
    local branch
    branch="$(git -C "$repo" branch --show-current)"
    if [[ -n "$branch" ]]; then
        printf '%s\n' "$branch"
    else
        printf 'DETACHED\n'
    fi
}

short_head() {
    git -C "$1" rev-parse --short=10 HEAD
}

tree_state() {
    if [[ -n "$(git -C "$1" status --porcelain)" ]]; then
        printf 'DIRTY\n'
    else
        printf 'clean\n'
    fi
}

upstream_state() {
    local repo="$1"
    local upstream counts ahead behind
    upstream="$(git -C "$repo" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)"
    if [[ -z "$upstream" ]]; then
        printf '%s\t%s\n' '-' 'no-upstream'
        return
    fi
    counts="$(git -C "$repo" rev-list --left-right --count "HEAD...$upstream" 2>/dev/null || true)"
    if [[ -z "$counts" ]]; then
        printf '%s\t%s\n' "$upstream" 'unknown'
        return
    fi
    read -r ahead behind <<< "$counts"
    if [[ "$ahead" == 0 && "$behind" == 0 ]]; then
        printf '%s\t%s\n' "$upstream" 'synced'
    else
        printf '%s\t%s\n' "$upstream" "+${ahead}/-${behind}"
    fi
}

root_pin() {
    local path="$1"
    local pin
    pin="$(git -C "$ROOT" ls-tree HEAD -- "$path" 2>/dev/null | awk '{print $3}')"
    if [[ -n "$pin" ]]; then
        printf '%.10s\n' "$pin"
    else
        printf '%s\n' '-'
    fi
}

is_repo_root() {
    local repo="$1"
    local top repo_real top_real
    [[ -d "$repo" ]] || return 1
    top="$(git -C "$repo" rev-parse --show-toplevel 2>/dev/null || true)"
    [[ -n "$top" ]] || return 1
    repo_real="$(cd "$repo" && pwd -P)"
    top_real="$(cd "$top" && pwd -P)"
    [[ "$repo_real" == "$top_real" ]]
}

STATUS_PROBLEMS=0

print_managed() {
    local label="$1"
    local repo="$2"
    local version_file="$3"
    local submodule_path="${4:-}"

    if ! is_repo_root "$repo"; then
        printf '%-15s %-8s %-15s %-15s %-10s %-10s %-11s %-6s %s\n' \
            "$label" '-' '-' '-' '-' '-' '-' '-' 'NOT-INITIALIZED'
        STATUS_PROBLEMS=$((STATUS_PROBLEMS + 1))
        return
    fi

    local version expected branch head pin tree upstream sync check
    version="$(read_version "$repo/$version_file" 2>/dev/null || true)"
    if [[ -n "$version" ]]; then
        expected="dev/$version"
    else
        version='?'
        expected='?'
    fi
    branch="$(branch_name "$repo")"
    head="$(short_head "$repo")"
    tree="$(tree_state "$repo")"
    IFS=$'\t' read -r upstream sync < <(upstream_state "$repo")

    if [[ -n "$submodule_path" ]]; then
        pin="$(root_pin "$submodule_path")"
    else
        pin='-'
    fi

    check='OK'
    if [[ "$version" == '?' ]]; then
        check='NO-VERSION'
    elif [[ "$branch" == 'DETACHED' ]]; then
        check='DETACHED'
    elif [[ "$branch" != "$expected" ]]; then
        check="BRANCH!=${expected}"
    fi

    if [[ -n "$submodule_path" && "$pin" != '-' && "$pin" != "$head" ]]; then
        if [[ "$check" == 'OK' ]]; then
            check='PIN!=HEAD'
        else
            check="${check},PIN!=HEAD"
        fi
    fi

    if [[ "$tree" == 'DIRTY' ]]; then
        if [[ "$check" == 'OK' ]]; then
            check='DIRTY'
        else
            check="${check},DIRTY"
        fi
    fi

    if [[ "$check" != 'OK' ]]; then
        STATUS_PROBLEMS=$((STATUS_PROBLEMS + 1))
    fi

    printf '%-15s %-8s %-15s %-15s %-10s %-10s %-11s %-6s %s\n' \
        "$label" "$version" "$branch" "$expected" "$head" "$pin" "$sync" "$tree" "$check"
    if [[ "$upstream" != '-' ]]; then
        printf '  upstream: %s\n' "$upstream"
    fi
}

print_other_submodule() {
    local path="$1"
    local repo="$ROOT/$path"
    if ! is_repo_root "$repo"; then
        printf '  %-34s %-15s %-10s %s\n' "$path" 'NOT-INITIALIZED' '-' '-'
        return
    fi
    printf '  %-34s %-15s %-10s %s\n' \
        "$path" "$(branch_name "$repo")" "$(short_head "$repo")" "$(tree_state "$repo")"
}

[[ -n "$ROOT" ]] || fail 'Could not determine IBEIS repository root'
[[ -d "$ROOT" ]] || fail "IBEIS root does not exist: $ROOT"
[[ -f "$ROOT/.gitmodules" ]] || fail "Missing $ROOT/.gitmodules"

printf 'IBEIS workspace: %s\n\n' "$ROOT"
printf '%-15s %-8s %-15s %-15s %-10s %-10s %-11s %-6s %s\n' \
    PACKAGE VERSION BRANCH EXPECTED HEAD PIN SYNC TREE CHECK
printf '%s\n' '----------------------------------------------------------------------------------------------------------------------'

print_managed 'utool'          "$ROOT/tpl/utool"          'utool/__init__.py'          'tpl/utool'
print_managed 'vtool_ibeis'    "$ROOT/tpl/vtool_ibeis"    'vtool_ibeis/__init__.py'    'tpl/vtool_ibeis'
print_managed 'dtool_ibeis'    "$ROOT/tpl/dtool_ibeis"    'dtool_ibeis/__init__.py'    'tpl/dtool_ibeis'
print_managed 'guitool_ibeis'  "$ROOT/tpl/guitool_ibeis"  'guitool_ibeis/__init__.py'  'tpl/guitool_ibeis'
print_managed 'plottool_ibeis' "$ROOT/tpl/plottool_ibeis" 'plottool_ibeis/__init__.py' 'tpl/plottool_ibeis'
print_managed 'ibeis'          "$ROOT"                    'ibeis/__init__.py'

if [[ "$SHOW_ALL_SUBMODULES" == 1 ]]; then
    echo
    echo 'Other initialized submodules:'
    printf '  %-34s %-15s %-10s %s\n' PATH BRANCH HEAD TREE
    declare -A managed=(
        [tpl/utool]=1
        [tpl/vtool_ibeis]=1
        [tpl/dtool_ibeis]=1
        [tpl/guitool_ibeis]=1
        [tpl/plottool_ibeis]=1
    )
    while read -r _ path; do
        [[ -n "${managed[$path]+x}" ]] && continue
        print_other_submodule "$path"
    done < <(git -C "$ROOT" config --file .gitmodules --get-regexp '^submodule\..*\.path$')
fi

echo
if (( STATUS_PROBLEMS == 0 )); then
    echo 'Managed package branches match their declared versions.'
else
    echo "$STATUS_PROBLEMS managed package(s) need attention."
fi

echo 'PIN is the submodule commit recorded by the current IBEIS HEAD; PIN!=HEAD means the root gitlink has not caught up yet.'
echo 'SYNC is relative to the configured upstream and does not fetch from the network.'

if [[ "$STRICT" == 1 && "$STATUS_PROBLEMS" != 0 ]]; then
    exit 1
fi
