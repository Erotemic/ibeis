#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
ROOT="${IBEIS_REPO:-$DEFAULT_ROOT}"
COAUTHOR="${COAUTHOR:-Co-authored-by: GPT-5.6 Sol <noreply@openai.com>}"

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

read_version() {
    python - "$1" <<'PY'
import pathlib
import re
import sys
path = pathlib.Path(sys.argv[1])
text = path.read_text()
m = re.search(r"(?m)^\s*__version__\s*=\s*(['\"])([^'\"]+)\1\s*(?:#.*)?$", text)
if not m:
    raise SystemExit(f'Could not find a simple __version__ assignment in {path}')
print(m.group(2))
PY
}

next_minor() {
    python - "$1" <<'PY'
import re
import sys
version = sys.argv[1]
m = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)', version)
if not m:
    raise SystemExit(f'Expected an X.Y.Z version, got {version!r}')
major, minor, patch = map(int, m.groups())
print(f'{major}.{minor + 1}.0')
PY
}

write_version() {
    python - "$1" "$2" <<'PY'
import pathlib
import re
import sys
path = pathlib.Path(sys.argv[1])
new_version = sys.argv[2]
text = path.read_text()
pattern = re.compile(
    r"(?m)^(?P<prefix>\s*__version__\s*=\s*)(?P<quote>['\"])(?P<version>[^'\"]+)(?P=quote)(?P<suffix>\s*(?:#.*)?)$"
)
matches = list(pattern.finditer(text))
if len(matches) != 1:
    raise SystemExit(f'Expected exactly one simple __version__ assignment in {path}, found {len(matches)}')
m = matches[0]
replacement = f"{m.group('prefix')}{m.group('quote')}{new_version}{m.group('quote')}{m.group('suffix')}"
text = text[:m.start()] + replacement + text[m.end():]
path.write_text(text)
PY
}

ensure_repo() {
    local repo="$1"
    [[ -d "$repo" ]] || fail "Repository directory does not exist: $repo"
    git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "Not a git repository: $repo"
}

ensure_version_file_clean() {
    local repo="$1"
    local version_file="$2"
    if ! git -C "$repo" diff --quiet -- "$version_file" || ! git -C "$repo" diff --cached --quiet -- "$version_file"; then
        fail "$repo/$version_file already has uncommitted changes; commit or stash them before bumping versions"
    fi
}

remote_branch_exists() {
    local repo="$1"
    local branch="$2"
    git -C "$repo" remote get-url origin >/dev/null 2>&1 || return 1
    git -C "$repo" ls-remote --exit-code --heads origin "$branch" >/dev/null 2>&1
}

switch_to_branch() {
    local repo="$1"
    local branch="$2"
    local current
    current="$(git -C "$repo" branch --show-current)"
    if [[ "$current" == "$branch" ]]; then
        return
    fi

    if git -C "$repo" show-ref --verify --quiet "refs/heads/$branch"; then
        git -C "$repo" switch "$branch"
    elif remote_branch_exists "$repo" "$branch"; then
        git -C "$repo" fetch origin "$branch"
        git -C "$repo" switch --track -c "$branch" "origin/$branch"
    else
        git -C "$repo" switch -c "$branch"
    fi
}

commit_only_paths() {
    local repo="$1"
    local subject="$2"
    shift 2
    local paths=("$@")

    git -C "$repo" add -A -- "${paths[@]}"
    if git -C "$repo" diff --cached --quiet -- "${paths[@]}"; then
        echo "  no commit needed"
        return
    fi
    git -C "$repo" commit --only \
        -m "$subject" \
        -m "$COAUTHOR" \
        -- "${paths[@]}"
}

prepare_package() {
    local label="$1"
    local repo="$2"
    local version_file="$3"

    echo
    echo "===== $label ====="
    ensure_repo "$repo"
    [[ -f "$repo/$version_file" ]] || fail "Missing version file: $repo/$version_file"
    ensure_version_file_clean "$repo" "$version_file"

    local current_version current_branch target_version target_branch
    current_version="$(read_version "$repo/$version_file")"
    current_branch="$(git -C "$repo" branch --show-current)"

    if [[ "$current_branch" == "dev/$current_version" ]]; then
        echo "  already prepared: $current_branch (__version__=$current_version)"
        return
    fi

    target_version="$(next_minor "$current_version")"
    target_branch="dev/$target_version"
    echo "  version: $current_version -> $target_version"
    echo "  branch:  ${current_branch:-DETACHED} -> $target_branch"

    switch_to_branch "$repo" "$target_branch"

    local branch_version
    branch_version="$(read_version "$repo/$version_file")"
    if [[ "$branch_version" == "$target_version" ]]; then
        echo "  target branch already has __version__=$target_version"
    elif [[ "$branch_version" == "$current_version" ]]; then
        write_version "$repo/$version_file" "$target_version"
    else
        fail "$label target branch has unexpected __version__=$branch_version (expected $current_version or $target_version)"
    fi

    commit_only_paths "$repo" "Bump version to $target_version" "$version_file"
}

prepare_root() {
    local repo="$ROOT"
    local version_file="ibeis/__init__.py"
    local gitlinks=(
        tpl/utool
        tpl/vtool_ibeis
        tpl/dtool_ibeis
        tpl/guitool_ibeis
        tpl/plottool_ibeis
    )

    echo
    echo "===== ibeis ====="
    ensure_repo "$repo"
    [[ -f "$repo/$version_file" ]] || fail "Missing version file: $repo/$version_file"
    ensure_version_file_clean "$repo" "$version_file"

    local current_version current_branch target_version target_branch did_bump=0
    current_version="$(read_version "$repo/$version_file")"
    current_branch="$(git -C "$repo" branch --show-current)"

    if [[ "$current_branch" == "dev/$current_version" ]]; then
        target_version="$current_version"
        target_branch="$current_branch"
        echo "  already on $target_branch (__version__=$target_version)"
    else
        target_version="$(next_minor "$current_version")"
        target_branch="dev/$target_version"
        echo "  version: $current_version -> $target_version"
        echo "  branch:  ${current_branch:-DETACHED} -> $target_branch"
        switch_to_branch "$repo" "$target_branch"

        local branch_version
        branch_version="$(read_version "$repo/$version_file")"
        if [[ "$branch_version" == "$target_version" ]]; then
            echo "  target branch already has __version__=$target_version"
        elif [[ "$branch_version" == "$current_version" ]]; then
            write_version "$repo/$version_file" "$target_version"
            did_bump=1
        else
            fail "IBEIS target branch has unexpected __version__=$branch_version (expected $current_version or $target_version)"
        fi
    fi

    local existing_paths=("$version_file")
    local path
    for path in "${gitlinks[@]}"; do
        [[ -e "$repo/$path" ]] || fail "Missing expected submodule path: $repo/$path"
        existing_paths+=("$path")
    done

    if (( did_bump )); then
        commit_only_paths "$repo" "Bump version to $target_version" "${existing_paths[@]}"
    else
        commit_only_paths "$repo" "Update dependency pins for $target_version" "${existing_paths[@]}"
    fi
}

[[ -d "$ROOT" ]] || fail "IBEIS root does not exist: $ROOT"

# Dependencies first so the IBEIS commit records their new gitlink SHAs.
prepare_package "utool"          "$ROOT/tpl/utool"          "utool/__init__.py"
prepare_package "vtool_ibeis"    "$ROOT/tpl/vtool_ibeis"    "vtool_ibeis/__init__.py"
prepare_package "dtool_ibeis"    "$ROOT/tpl/dtool_ibeis"    "dtool_ibeis/__init__.py"
prepare_package "guitool_ibeis"  "$ROOT/tpl/guitool_ibeis"  "guitool_ibeis/__init__.py"
prepare_package "plottool_ibeis" "$ROOT/tpl/plottool_ibeis" "plottool_ibeis/__init__.py"
prepare_root

echo
echo "Prepared development branches:"
printf '  %-36s %s\n' "tpl/utool" "$(git -C "$ROOT/tpl/utool" branch --show-current)"
printf '  %-36s %s\n' "tpl/vtool_ibeis" "$(git -C "$ROOT/tpl/vtool_ibeis" branch --show-current)"
printf '  %-36s %s\n' "tpl/dtool_ibeis" "$(git -C "$ROOT/tpl/dtool_ibeis" branch --show-current)"
printf '  %-36s %s\n' "tpl/guitool_ibeis" "$(git -C "$ROOT/tpl/guitool_ibeis" branch --show-current)"
printf '  %-36s %s\n' "tpl/plottool_ibeis" "$(git -C "$ROOT/tpl/plottool_ibeis" branch --show-current)"
printf '  %-36s %s\n' "ibeis" "$(git -C "$ROOT" branch --show-current)"
