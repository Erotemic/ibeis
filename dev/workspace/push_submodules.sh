#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
ROOT="${IBEIS_REPO:-$DEFAULT_ROOT}"
REMOTE="${REMOTE:-origin}"
INCLUDE_ROOT="${INCLUDE_ROOT:-1}"
PUSH_ANY_BRANCH="${PUSH_ANY_BRANCH:-0}"
DRY_RUN="${DRY_RUN:-0}"

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

run() {
    printf '+'
    printf ' %q' "$@"
    printf '\n'
    if [[ "$DRY_RUN" != 1 ]]; then
        "$@"
    fi
}

mapfile -t ALL_PATHS < <(
    git -C "$ROOT" config --file .gitmodules --get-regexp '^submodule\..*\.path$' \
        | awk '{print $2}'
)

# Put the release-sensitive dependencies first, then any remaining initialized
# submodules. IBEIS itself is pushed last when INCLUDE_ROOT=1.
PRIORITY=(
    tpl/utool
    tpl/vtool_ibeis
    tpl/dtool_ibeis
    tpl/guitool_ibeis
    tpl/plottool_ibeis
)

ordered_paths=()
declare -A seen=()
for path in "${PRIORITY[@]}"; do
    for candidate in "${ALL_PATHS[@]}"; do
        if [[ "$candidate" == "$path" ]]; then
            ordered_paths+=("$path")
            seen["$path"]=1
            break
        fi
    done
done
for path in "${ALL_PATHS[@]}"; do
    if [[ -z "${seen[$path]+x}" ]]; then
        ordered_paths+=("$path")
    fi
done

push_repo() {
    local label="$1"
    local repo="$2"

    if ! git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        echo "SKIP $label: not initialized"
        return
    fi

    local branch
    branch="$(git -C "$repo" branch --show-current)"
    if [[ -z "$branch" ]]; then
        echo "SKIP $label: detached HEAD"
        return
    fi
    if [[ "$PUSH_ANY_BRANCH" != 1 && "$branch" != dev/* ]]; then
        echo "SKIP $label: branch '$branch' is not dev/* (set PUSH_ANY_BRANCH=1 to override)"
        return
    fi
    git -C "$repo" remote get-url "$REMOTE" >/dev/null 2>&1 || fail "$label has no remote '$REMOTE'"

    if [[ -n "$(git -C "$repo" status --porcelain)" ]]; then
        echo "WARN $label: working tree is dirty; pushing committed HEAD only"
    fi

    echo "PUSH $label: $branch"
    run git -C "$repo" push -u "$REMOTE" "$branch"
}

[[ -d "$ROOT" ]] || fail "IBEIS root does not exist: $ROOT"
[[ -f "$ROOT/.gitmodules" ]] || fail "Missing $ROOT/.gitmodules"

for path in "${ordered_paths[@]}"; do
    push_repo "$path" "$ROOT/$path"
done

if [[ "$INCLUDE_ROOT" == 1 ]]; then
    push_repo "ibeis" "$ROOT"
fi
