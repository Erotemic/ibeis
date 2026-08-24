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

next_minor_version() {
    local version="$1"
    python - "$version" <<'PY'
import re
import sys
version = sys.argv[1]
match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
if not match:
    raise SystemExit(1)
major, minor, _patch = map(int, match.groups())
print(f"{major}.{minor + 1}.0")
PY
}

branch_name() {
    local branch
    branch="$(git -C "$1" branch --show-current)"
    [[ -n "$branch" ]] && printf '%s\n' "$branch" || printf 'DETACHED\n'
}

short_head() {
    git -C "$1" rev-parse --short=10 HEAD
}

tree_state() {
    [[ -n "$(git -C "$1" status --porcelain)" ]] && printf 'DIRTY\n' || printf 'clean\n'
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

preferred_remote() {
    local repo="$1"
    local upstream remote
    upstream="$(git -C "$repo" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)"
    if [[ "$upstream" == */* ]]; then
        remote="${upstream%%/*}"
        if git -C "$repo" remote get-url "$remote" >/dev/null 2>&1; then
            printf '%s\n' "$remote"
            return
        fi
    fi
    for remote in origin Erotemic; do
        if git -C "$repo" remote get-url "$remote" >/dev/null 2>&1; then
            printf '%s\n' "$remote"
            return
        fi
    done
    remote="$(git -C "$repo" remote | head -n 1)"
    printf '%s\n' "$remote"
}

main_state() {
    local repo="$1"
    local remote main_ref counts ahead behind
    remote="$(preferred_remote "$repo")"
    [[ -n "$remote" ]] || { printf '%s\n' 'no-remote'; return; }
    main_ref="$remote/main"
    git -C "$repo" rev-parse --verify --quiet "$main_ref^{commit}" >/dev/null 2>&1 || {
        printf '%s\n' 'no-main-ref'
        return
    }
    if git -C "$repo" merge-base --is-ancestor HEAD "$main_ref" 2>/dev/null; then
        printf '%s\n' 'merged'
        return
    fi
    counts="$(git -C "$repo" rev-list --left-right --count "HEAD...$main_ref" 2>/dev/null || true)"
    [[ -n "$counts" ]] || { printf '%s\n' 'unknown'; return; }
    read -r ahead behind <<< "$counts"
    printf '+%s/-%s\n' "$ahead" "$behind"
}

root_pin() {
    local path="$1"
    local pin
    pin="$(git -C "$ROOT" ls-tree HEAD -- "$path" 2>/dev/null | awk '{print $3}')"
    [[ -n "$pin" ]] && printf '%.10s\n' "$pin" || printf '%s\n' '-'
}

is_repo_root() {
    local repo="$1"
    local top
    [[ -d "$repo" ]] || return 1
    top="$(git -C "$repo" rev-parse --show-toplevel 2>/dev/null || true)"
    [[ -n "$top" ]] || return 1
    [[ "$(cd "$repo" && pwd -P)" == "$(cd "$top" && pwd -P)" ]]
}

STATUS_PROBLEMS=0

print_managed() {
    local label="$1"
    local repo="$2"
    local version_file="$3"
    local submodule_path="${4:-}"

    if ! is_repo_root "$repo"; then
        printf '%-15s %-8s %-8s %-15s %-15s %-10s %-10s %-10s %-11s %-6s %s\n' \
            "$label" '-' '-' '-' '-' '-' '-' '-' '-' '-' 'NOT-INITIALIZED'
        STATUS_PROBLEMS=$((STATUS_PROBLEMS + 1))
        return
    fi

    local version target_version expected branch head pin tree upstream sync main check
    version="$(read_version "$repo/$version_file" 2>/dev/null || true)"
    [[ -n "$version" ]] || version='?'
    branch="$(branch_name "$repo")"

    if [[ "$branch" == dev/* ]]; then
        target_version="${branch#dev/}"
        expected="$branch"
    elif [[ "$version" != '?' ]]; then
        target_version="$(next_minor_version "$version" 2>/dev/null || true)"
        if [[ -n "$target_version" ]]; then
            expected="dev/$target_version"
        else
            target_version='?'
            expected='?'
        fi
    else
        target_version='?'
        expected='?'
    fi

    head="$(short_head "$repo")"
    tree="$(tree_state "$repo")"
    IFS=$'\t' read -r upstream sync < <(upstream_state "$repo")
    main="$(main_state "$repo")"
    [[ -n "$submodule_path" ]] && pin="$(root_pin "$submodule_path")" || pin='-'

    check='OK'
    if [[ "$version" == '?' ]]; then
        check='NO-VERSION'
    elif [[ "$target_version" == '?' ]]; then
        check='BAD-VERSION'
    elif [[ "$branch" == 'DETACHED' ]]; then
        check='DETACHED'
    elif [[ "$branch" == dev/* && "$version" != "$target_version" ]]; then
        check="VERSION!=${target_version}"
    elif [[ "$branch" != "$expected" ]]; then
        check="BRANCH!=${expected}"
    fi

    if [[ -n "$submodule_path" && "$pin" != '-' && "$pin" != "$head" ]]; then
        [[ "$check" == OK ]] && check='PIN!=HEAD' || check="${check},PIN!=HEAD"
    fi
    [[ "$check" == OK ]] || STATUS_PROBLEMS=$((STATUS_PROBLEMS + 1))

    printf '%-15s %-8s %-8s %-15s %-15s %-10s %-10s %-10s %-11s %-6s %s\n' \
        "$label" "$version" "$target_version" "$branch" "$expected" "$head" "$pin" "$main" "$sync" "$tree" "$check"
    [[ "$upstream" == '-' ]] || printf '  upstream: %s\n' "$upstream"
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
printf '%-15s %-8s %-8s %-15s %-15s %-10s %-10s %-10s %-11s %-6s %s\n' \
    PACKAGE VERSION TARGET BRANCH EXPECTED HEAD PIN MAIN SYNC TREE CHECK
printf '%s\n' '--------------------------------------------------------------------------------------------------------------------------------------------'

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
    echo 'Managed package versions and branches match the release-preparation target.'
else
    echo "$STATUS_PROBLEMS managed package(s) need attention."
fi

echo 'TARGET is the dev-branch version when already on dev/*; otherwise it is the next minor version of the declared package version.'
echo 'PIN is the submodule commit recorded by the current IBEIS HEAD; PIN!=HEAD means the root gitlink has not caught up yet.'
echo 'MAIN is the relation to the locally cached upstream main: merged means HEAD is already contained by main; +N/-M means branch-only/main-only commits.'
echo 'SYNC is relative to the configured upstream and does not fetch from the network.'
echo 'TREE is informational: unrelated tracked edits and untracked drafts are allowed and do not make CHECK fail.'

if [[ "$STRICT" == 1 && "$STATUS_PROBLEMS" != 0 ]]; then
    exit 1
fi
