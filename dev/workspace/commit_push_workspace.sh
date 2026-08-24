#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
ROOT="${IBEIS_REPO:-$DEFAULT_ROOT}"
MODE="review"
ASSUME_YES=0
DO_PUSH=1
ALLOW_ANY_BRANCH=0
MESSAGE="${MESSAGE:-Ecosystem maintenance}"
COAUTHOR="${COAUTHOR:-Co-authored-by: GPT-5.6 Sol <noreply@openai.com>}"

usage() {
    cat <<'USAGE'
Usage:
    dev/workspace/commit_push_workspace.sh
    dev/workspace/commit_push_workspace.sh --apply
    dev/workspace/commit_push_workspace.sh --apply --yes

Default mode is review-only. It prints the exact dirty files in each initialized
submodule and in IBEIS, along with any branch change that would be made. It does
not stage, commit, switch branches, or push anything.

Options:
    --apply             Perform branch preparation, then review/stage/commit each
                        dirty repository, commit IBEIS last, and push at the end.
    --yes               Select every reviewed path without prompting. Without
                        this flag, each repo offers all / select / skip.
    --no-push           Commit locally but do not push.
    --allow-any-branch  Allow committing a dirty repository on a non-main,
                        non-master, non-dev/* branch.
    --message TEXT      Commit subject to use in every repository.
    -h, --help          Show this help.

Environment:
    IBEIS_REPO          Override the IBEIS checkout root.
    MESSAGE             Default commit subject.
    COAUTHOR            Override the commit trailer.

Safety properties:
  * No blind `git add -A` across a repository.
  * The script snapshots and prints the exact dirty paths first.
  * On apply, only selected reviewed paths are passed to `git add -A -- <paths>`.
  * Commits use `git commit --only -- <selected paths>`, so unrelated content
    that was already staged before the script is not swept into the commit.
  * Repositories with merge conflicts are refused.
  * IBEIS is committed last, after submodule HEADs are finalized, so gitlinks
    record the commits that were actually made.
USAGE
}

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

run() {
    printf '+'
    printf ' %q' "$@"
    printf '\n'
    "$@"
}

confirm() {
    local prompt="$1"
    if [[ "$ASSUME_YES" == 1 ]]; then
        return 0
    fi
    local reply
    read -r -p "$prompt [y/N] " reply
    [[ "$reply" == y || "$reply" == Y || "$reply" == yes || "$reply" == YES ]]
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
m = re.search(
    r"(?m)^\s*__version__\s*=\s*(['\"])([^'\"]+)\1\s*(?:#.*)?$",
    text,
)
if not m:
    raise SystemExit(1)
print(m.group(2))
PY
}

next_minor() {
    python - "$1" <<'PY'
import re
import sys
m = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)', sys.argv[1])
if not m:
    raise SystemExit(1)
major, minor, _patch = map(int, m.groups())
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
    raise SystemExit(
        f'Expected exactly one simple __version__ assignment in {path}, '
        f'found {len(matches)}'
    )
m = matches[0]
replacement = (
    f"{m.group('prefix')}{m.group('quote')}{new_version}"
    f"{m.group('quote')}{m.group('suffix')}"
)
path.write_text(text[:m.start()] + replacement + text[m.end():])
PY
}

version_file_for_path() {
    local path="$1"
    case "$path" in
        tpl/utool)           printf '%s\n' 'utool/__init__.py' ;;
        tpl/vtool_ibeis)     printf '%s\n' 'vtool_ibeis/__init__.py' ;;
        tpl/dtool_ibeis)     printf '%s\n' 'dtool_ibeis/__init__.py' ;;
        tpl/guitool_ibeis)   printf '%s\n' 'guitool_ibeis/__init__.py' ;;
        tpl/plottool_ibeis)  printf '%s\n' 'plottool_ibeis/__init__.py' ;;
        tpl/pyhesaff)        printf '%s\n' 'pyhesaff/__init__.py' ;;
        tpl/pyflann_ibeis)   printf '%s\n' 'pyflann_ibeis/__init__.py' ;;
        tpl/vtool_ibeis_ext) printf '%s\n' 'vtool_ibeis_ext/__init__.py' ;;
        .)                   printf '%s\n' 'ibeis/__init__.py' ;;
        *)                   return 1 ;;
    esac
}

is_repo_root() {
    local repo="$1"
    local top
    [[ -d "$repo" ]] || return 1
    top="$(git -C "$repo" rev-parse --show-toplevel 2>/dev/null || true)"
    [[ -n "$top" ]] || return 1
    [[ "$(cd "$repo" && pwd -P)" == "$(cd "$top" && pwd -P)" ]]
}

collect_dirty_paths() {
    local repo="$1"
    python - "$repo" <<'PY'
import os
import subprocess
import sys
repo = sys.argv[1]
commands = [
    ['git', '-C', repo, 'diff', '--cached', '--name-only', '-z'],
    ['git', '-C', repo, 'diff', '--name-only', '-z'],
    ['git', '-C', repo, 'ls-files', '--others', '--exclude-standard', '-z'],
]
seen = set()
paths = []
for cmd in commands:
    data = subprocess.check_output(cmd)
    for raw in data.split(b'\0'):
        if not raw:
            continue
        path = os.fsdecode(raw)
        if path not in seen:
            seen.add(path)
            paths.append(path)
for path in paths:
    sys.stdout.buffer.write(os.fsencode(path) + b'\0')
PY
}

has_dirty_paths() {
    local repo="$1"
    [[ -n "$(git -C "$repo" status --porcelain --untracked-files=normal)" ]]
}

has_conflicts() {
    local repo="$1"
    [[ -n "$(git -C "$repo" ls-files -u)" ]]
}

select_remote() {
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
    [[ -n "$remote" ]] || fail "$repo has no Git remotes"
    printf '%s\n' "$remote"
}

remote_branch_exists() {
    local repo="$1"
    local remote="$2"
    local branch="$3"
    git -C "$repo" ls-remote --exit-code --heads "$remote" "$branch" >/dev/null 2>&1
}

proposal_for_repo() {
    local path="$1"
    local repo="$2"
    local branch version_file version target
    branch="$(git -C "$repo" branch --show-current)"
    version_file="$(version_file_for_path "$path" 2>/dev/null || true)"
    version=""
    if [[ -n "$version_file" ]]; then
        version="$(read_version "$repo/$version_file" 2>/dev/null || true)"
    fi

    if [[ "$branch" == dev/* ]]; then
        printf 'keep branch %s' "$branch"
    elif [[ "$branch" == main || "$branch" == master ]]; then
        if [[ -n "$version" ]]; then
            target="$(next_minor "$version" 2>/dev/null || true)"
            if [[ -n "$target" ]]; then
                printf 'switch %s -> dev/%s and bump %s -> %s' \
                    "$branch" "$target" "$version" "$target"
            else
                printf 'cannot infer next dev branch from version %s' "$version"
            fi
        else
            printf 'cannot infer version/target branch'
        fi
    elif [[ -z "$branch" ]]; then
        printf 'detached HEAD (apply will refuse)'
    else
        printf 'keep nonstandard branch %s%s' "$branch" \
            "$([[ "$ALLOW_ANY_BRANCH" == 1 ]] && printf ' (--allow-any-branch)' || printf ' (apply will refuse)')"
    fi
    printf '\n'
}

print_repo_review() {
    local label="$1"
    local path="$2"
    local repo="$3"
    local branch head
    branch="$(git -C "$repo" branch --show-current)"
    [[ -n "$branch" ]] || branch='DETACHED'
    head="$(git -C "$repo" rev-parse --short=10 HEAD)"

    echo
    echo "===== $label ====="
    echo "repo:     $repo"
    echo "branch:   $branch"
    echo "head:     $head"
    printf 'proposal: '
    proposal_for_repo "$path" "$repo"
    echo "status:"
    if has_dirty_paths "$repo"; then
        git -C "$repo" status --short --untracked-files=normal | sed 's/^/  /'
    else
        echo "  clean"
    fi
}

prepare_branch() {
    local label="$1"
    local path="$2"
    local repo="$3"
    local branch version_file version target target_branch remote branch_version

    branch="$(git -C "$repo" branch --show-current)"
    [[ -n "$branch" ]] || fail "$label is on detached HEAD"

    if [[ "$branch" == dev/* ]]; then
        return
    fi
    if [[ "$branch" != main && "$branch" != master ]]; then
        [[ "$ALLOW_ANY_BRANCH" == 1 ]] || \
            fail "$label is on nonstandard branch '$branch'; use --allow-any-branch to commit there"
        return
    fi

    version_file="$(version_file_for_path "$path" 2>/dev/null || true)"
    [[ -n "$version_file" ]] || fail "$label has no configured version file for automatic dev-branch creation"
    version="$(read_version "$repo/$version_file" 2>/dev/null || true)"
    [[ -n "$version" ]] || fail "Could not read version from $repo/$version_file"
    target="$(next_minor "$version" 2>/dev/null || true)"
    [[ -n "$target" ]] || fail "Could not compute next minor version from $version"
    target_branch="dev/$target"
    remote="$(select_remote "$repo")"

    echo "  preparing $label: $branch -> $target_branch"
    if git -C "$repo" show-ref --verify --quiet "refs/heads/$target_branch"; then
        git -C "$repo" merge-base --is-ancestor HEAD "$target_branch" || \
            fail "$label local $target_branch does not contain current HEAD; refusing automatic switch"
        run git -C "$repo" switch "$target_branch"
    elif remote_branch_exists "$repo" "$remote" "$target_branch"; then
        run git -C "$repo" fetch "$remote" "$target_branch"
        git -C "$repo" merge-base --is-ancestor HEAD "$remote/$target_branch" || \
            fail "$label remote $remote/$target_branch does not contain current HEAD; refusing automatic switch"
        run git -C "$repo" switch --track -c "$target_branch" "$remote/$target_branch"
    else
        run git -C "$repo" switch -c "$target_branch"
    fi

    branch_version="$(read_version "$repo/$version_file" 2>/dev/null || true)"
    if [[ "$branch_version" == "$target" ]]; then
        echo "  $version_file is already $target"
    elif [[ "$branch_version" == "$version" ]]; then
        echo "  bumping $version_file: $version -> $target"
        write_version "$repo/$version_file" "$target"
    else
        fail "$label has unexpected version $branch_version after switching to $target_branch"
    fi
}

stage_reviewed_paths() {
    local label="$1"
    local repo="$2"
    shift 2
    local paths=("$@")
    ((${#paths[@]} > 0)) || return 1

    echo "  reviewed dirty paths:"
    local path
    for path in "${paths[@]}"; do
        printf '    %s\n' "$path"
    done

    local -a selected=()
    if [[ "$ASSUME_YES" == 1 ]]; then
        selected=("${paths[@]}")
    else
        local choice
        read -r -p "Stage paths in $label? [a]ll / [s]elect / [n]one: " choice
        case "$choice" in
            a|A|all|ALL)
                selected=("${paths[@]}")
                ;;
            s|S|select|SELECT)
                local answer
                for path in "${paths[@]}"; do
                    read -r -p "  include '$path'? [y/N] " answer
                    if [[ "$answer" == y || "$answer" == Y || "$answer" == yes || "$answer" == YES ]]; then
                        selected+=("$path")
                    fi
                done
                ;;
            *)
                echo "  SKIP $label"
                return 1
                ;;
        esac
    fi

    if ((${#selected[@]} == 0)); then
        echo "  SKIP $label: no paths selected"
        return 1
    fi

    echo "  exact selected paths to stage and commit:"
    for path in "${selected[@]}"; do
        printf '    %s\n' "$path"
    done

    run git -C "$repo" add -A -- "${selected[@]}"

    # --only is intentional: pre-existing staged changes outside the selected
    # path set remain staged but are not included in this commit.
    if git -C "$repo" diff --quiet HEAD -- "${selected[@]}"; then
        echo "  no selected change remains in $label"
        return 1
    fi

    run git -C "$repo" commit --only \
        -m "$MESSAGE" \
        -m "$COAUTHOR" \
        -- "${selected[@]}"

    # Assert that the commit we just made did not pick up anything outside the
    # path set the user selected.
    python - "$repo" "${selected[@]}" <<'PYCHECK'
import os
import subprocess
import sys
repo = sys.argv[1]
approved = set(sys.argv[2:])
data = subprocess.check_output(
    ['git', '-C', repo, 'diff-tree', '--no-commit-id', '--name-only', '-r', '-z', 'HEAD']
)
committed = {os.fsdecode(p) for p in data.split(b'\0') if p}
extra = sorted(committed - approved)
if extra:
    print('ERROR: commit contains paths outside selected set:', file=sys.stderr)
    for path in extra:
        print(f'  {path}', file=sys.stderr)
    raise SystemExit(1)
PYCHECK
    return 0
}

process_repo() {
    local label="$1"
    local path="$2"
    local repo="$3"

    has_dirty_paths "$repo" || {
        echo "SKIP $label: clean"
        return 0
    }

    prepare_branch "$label" "$path" "$repo"
    print_repo_review "$label" "$path" "$repo"

    local -a paths=()
    mapfile -d '' -t paths < <(collect_dirty_paths "$repo")
    stage_reviewed_paths "$label" "$repo" "${paths[@]}" || true
}

while (($#)); do
    case "$1" in
        --apply)
            MODE="apply"
            shift
            ;;
        --yes|-y)
            ASSUME_YES=1
            shift
            ;;
        --no-push)
            DO_PUSH=0
            shift
            ;;
        --allow-any-branch)
            ALLOW_ANY_BRANCH=1
            shift
            ;;
        --message)
            (($# >= 2)) || fail '--message requires an argument'
            MESSAGE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "Unknown argument: $1"
            ;;
    esac
done

[[ -n "$ROOT" ]] || fail 'Could not determine IBEIS repository root'
[[ -d "$ROOT" ]] || fail "IBEIS root does not exist: $ROOT"
[[ -f "$ROOT/.gitmodules" ]] || fail "Missing $ROOT/.gitmodules"

mapfile -t ALL_PATHS < <(
    git -C "$ROOT" config --file .gitmodules --get-regexp '^submodule\..*\.path$' \
        | awk '{print $2}'
)

PRIORITY=(
    tpl/utool
    tpl/vtool_ibeis
    tpl/dtool_ibeis
    tpl/guitool_ibeis
    tpl/plottool_ibeis
    tpl/pyhesaff
    tpl/pyflann_ibeis
    tpl/vtool_ibeis_ext
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

# Global preflight: show everything before apply mutates anything, and refuse
# unresolved merge conflicts up front.
echo "IBEIS workspace: $ROOT"
echo "mode: $MODE"
echo "commit message: $MESSAGE"
for path in "${ordered_paths[@]}"; do
    repo="$ROOT/$path"
    if ! is_repo_root "$repo"; then
        echo
        echo "===== $path ====="
        echo "SKIP: not initialized"
        continue
    fi
    has_conflicts "$repo" && fail "$path has unresolved merge conflicts"
    print_repo_review "$path" "$path" "$repo"
done
has_conflicts "$ROOT" && fail "ibeis has unresolved merge conflicts"
print_repo_review "ibeis" "." "$ROOT"

if [[ "$MODE" == review ]]; then
    echo
    echo 'Review only: nothing was staged, committed, switched, or pushed.'
    echo 'Run again with --apply when the paths above look correct.'
    exit 0
fi

if ! confirm 'Proceed with branch preparation and per-repository staging review?'; then
    echo 'Aborted without changes.'
    exit 0
fi

# Commit submodules first so the root commit records their final HEADs.
for path in "${ordered_paths[@]}"; do
    repo="$ROOT/$path"
    is_repo_root "$repo" || continue
    process_repo "$path" "$path" "$repo"
done

# Recompute and review the root after submodule commits. This is where changed
# gitlinks appear, alongside any pre-existing IBEIS changes.
process_repo "ibeis" "." "$ROOT"

if [[ "$DO_PUSH" == 1 ]]; then
    echo
    echo '===== push ====='
    if [[ -x "$SCRIPT_DIR/push_submodules.sh" ]]; then
        INCLUDE_ROOT=1 PUSH_ANY_BRANCH="$ALLOW_ANY_BRANCH" \
            "$SCRIPT_DIR/push_submodules.sh"
    else
        echo 'push_submodules.sh is unavailable; pushing repositories directly.'
        for path in "${ordered_paths[@]}"; do
            repo="$ROOT/$path"
            is_repo_root "$repo" || continue
            branch="$(git -C "$repo" branch --show-current)"
            [[ -n "$branch" ]] || continue
            if [[ "$branch" != dev/* && "$ALLOW_ANY_BRANCH" != 1 ]]; then
                continue
            fi
            remote="$(select_remote "$repo")"
            run git -C "$repo" push -u "$remote" "$branch"
        done
        branch="$(git -C "$ROOT" branch --show-current)"
        remote="$(select_remote "$ROOT")"
        run git -C "$ROOT" push -u "$remote" "$branch"
    fi
fi

echo
if [[ -x "$SCRIPT_DIR/workspace_status.sh" ]]; then
    "$SCRIPT_DIR/workspace_status.sh" || true
else
    git -C "$ROOT" status --short --branch
fi
