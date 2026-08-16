#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
ROOT="${IBEIS_REPO:-$DEFAULT_ROOT}"
REMOTE="${REMOTE:-origin}"
INCLUDE_ROOT="${INCLUDE_ROOT:-0}"
PULL_ANY_BRANCH="${PULL_ANY_BRANCH:-0}"
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

pull_repo() {
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
    if [[ "$PULL_ANY_BRANCH" != 1 && "$branch" != dev/* ]]; then
        echo "SKIP $label: branch '$branch' is not dev/* (set PULL_ANY_BRANCH=1 to override)"
        return
    fi
    git -C "$repo" remote get-url "$REMOTE" >/dev/null 2>&1 || fail "$label has no remote '$REMOTE'"

    if [[ -n "$(git -C "$repo" status --porcelain)" ]]; then
        echo "SKIP $label: dirty working tree"
        return
    fi

    echo "PULL $label: $branch"
    run git -C "$repo" fetch "$REMOTE" "$branch"
    run git -C "$repo" merge --ff-only "$REMOTE/$branch"
}

[[ -d "$ROOT" ]] || fail "IBEIS root does not exist: $ROOT"
[[ -f "$ROOT/.gitmodules" ]] || fail "Missing $ROOT/.gitmodules"

# If requested, update the superproject first. We deliberately do not run
# `git submodule update`: that would detach the development branch checkouts.
if [[ "$INCLUDE_ROOT" == 1 ]]; then
    pull_repo "ibeis" "$ROOT"
fi

for path in "${ALL_PATHS[@]}"; do
    pull_repo "$path" "$ROOT/$path"
done

echo
if [[ "$DRY_RUN" != 1 ]]; then
    echo "Superproject gitlink status after submodule pulls:"
    git -C "$ROOT" status --short --ignore-submodules=none
fi
