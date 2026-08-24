#!/usr/bin/env bash
set -euo pipefail

# One-off recovery/release helper for the coordinated inject2 -> Loguru refactor.
#
# Ambient workspace policy: unrelated tracked edits and untracked drafts are
# preserved. Only explicit release paths are staged/committed. Git is allowed
# to reject a branch switch if an ambient file would actually be overwritten.
#
# This script is intentionally state-aware. It knows the commits that anchored
# the migration when the multi-repository refactor was published and refuses to
# rewrite or merge around them if the remote history no longer contains those
# anchors.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
ROOT="${IBEIS_REPO:-$DEFAULT_ROOT}"
OWNER="${GITHUB_OWNER:-Erotemic}"
YES="${YES:-0}"
CREATE_PRS="${CREATE_PRS:-1}"
DRAFT_PRS="${DRAFT_PRS:-1}"
COAUTHOR="${COAUTHOR:-Co-authored-by: GPT-5.6 Thinking <noreply@openai.com>}"

# Known migration anchors. These make the one-off recovery conservative: if the
# remote histories no longer contain what we expect, stop and reassess instead
# of guessing.
UTOOL_LOGURU_ANCHOR="${UTOOL_LOGURU_ANCHOR:-5adab87fed666c3465456ff0a863e4bdccf2d20f}"
VTOOL_LOGURU_ANCHOR="${VTOOL_LOGURU_ANCHOR:-460addd1f97c78c8e5f6241dbd568e2bb7ee2299}"
DTOOL_LOGURU_ANCHOR="${DTOOL_LOGURU_ANCHOR:-16ec663f66a84469eecd43ebc1441fd287052ef7}"
GUITOOL_LOGURU_ANCHOR="${GUITOOL_LOGURU_ANCHOR:-d3654296ed512ee75f839fe9e2f82f406f4130be}"
PLOTTOOL_LOGURU_ANCHOR="${PLOTTOOL_LOGURU_ANCHOR:-343493a03765003a42499cc4b473d31ccb3780f3}"
IBEIS_LOGURU_ANCHOR="${IBEIS_LOGURU_ANCHOR:-5a986e1963436e94b8c081c5b3f7d362e68d7d95}"
IBEIS_OLD_HOT_RELOAD_ANCHOR="${IBEIS_OLD_HOT_RELOAD_ANCHOR:-ffad8560dc8162e5beefcce66f07f02618685a15}"
ALLOW_ANY_REMOTE="${ALLOW_ANY_REMOTE:-0}"

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

note() {
    printf '  %s\n' "$*"
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "Required command is not installed: $1"
}

repo_top() {
    git -C "$1" rev-parse --show-toplevel 2>/dev/null || true
}

ensure_repo() {
    local repo="$1"
    [[ -d "$repo" ]] || fail "Repository directory does not exist: $repo"
    local top
    top="$(repo_top "$repo")"
    [[ -n "$top" ]] || fail "Not a Git repository: $repo"
    [[ "$(cd "$repo" && pwd -P)" == "$(cd "$top" && pwd -P)" ]] || \
        fail "Expected repository root at $repo, but Git root is $top"
}

remote_url_matches() {
    local url="$1"
    local slug="$2"
    case "$url" in
        *github.com[:/]"$OWNER"/"$slug"|*github.com[:/]"$OWNER"/"$slug".git)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

find_remote() {
    local repo="$1"
    local slug="$2"
    local remote url

    # Prefer the conventional names when they point at the expected upstream.
    for remote in origin "$OWNER"; do
        if git -C "$repo" remote get-url "$remote" >/dev/null 2>&1; then
            url="$(git -C "$repo" remote get-url "$remote")"
            if remote_url_matches "$url" "$slug"; then
                printf '%s\n' "$remote"
                return 0
            fi
        fi
    done

    while IFS= read -r remote; do
        [[ -n "$remote" ]] || continue
        url="$(git -C "$repo" remote get-url "$remote" 2>/dev/null || true)"
        if remote_url_matches "$url" "$slug"; then
            printf '%s\n' "$remote"
            return 0
        fi
    done < <(git -C "$repo" remote)

    if [[ "$ALLOW_ANY_REMOTE" == 1 ]]; then
        if git -C "$repo" remote get-url origin >/dev/null 2>&1; then
            printf '%s\n' origin
            return 0
        fi
        remote="$(git -C "$repo" remote | head -n 1)"
        if [[ -n "$remote" ]]; then
            printf '%s\n' "$remote"
            return 0
        fi
    fi

    fail "Could not find a Git remote for $OWNER/$slug in $repo"
}

remote_branch_ref() {
    printf '%s/%s\n' "$1" "$2"
}

ref_exists() {
    git -C "$1" rev-parse --verify --quiet "$2^{commit}" >/dev/null 2>&1
}

ensure_ancestor() {
    local repo="$1"
    local ancestor="$2"
    local descendant="$3"
    local what="$4"
    ref_exists "$repo" "$ancestor" || fail "$what anchor is not available locally after fetch: $ancestor"
    ref_exists "$repo" "$descendant" || fail "$what target ref is not available after fetch: $descendant"
    git -C "$repo" merge-base --is-ancestor "$ancestor" "$descendant" || \
        fail "$what is missing expected migration anchor $ancestor in $descendant"
}

fetch_repo() {
    local label="$1"
    local repo="$2"
    local slug="$3"
    local outvar="$4"
    local remote
    remote="$(find_remote "$repo" "$slug")"
    echo "===== fetch $label ($remote) ====="
    git -C "$repo" fetch "$remote" --prune
    printf -v "$outvar" '%s' "$remote"
}

read_version() {
    python - "$1" <<'PY'
import pathlib
import re
import sys
path = pathlib.Path(sys.argv[1])
text = path.read_text()
match = re.search(r"(?m)^\s*__version__\s*=\s*(['\"])([^'\"]+)\1\s*(?:#.*)?$", text)
if not match:
    raise SystemExit(f'Could not find a simple __version__ assignment in {path}')
print(match.group(2))
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
match = matches[0]
replacement = (
    f"{match.group('prefix')}{match.group('quote')}{new_version}"
    f"{match.group('quote')}{match.group('suffix')}"
)
path.write_text(text[:match.start()] + replacement + text[match.end():])
PY
}

ensure_path_clean() {
    local label="$1"
    local repo="$2"
    local path="$3"
    if ! git -C "$repo" diff --quiet -- "$path" || ! git -C "$repo" diff --cached --quiet -- "$path"; then
        fail "$label path already has uncommitted changes: $path"
    fi
}

commit_paths_if_needed() {
    local repo="$1"
    local subject="$2"
    local body="$3"
    shift 3
    local paths=("$@")

    git -C "$repo" add -A -- "${paths[@]}"
    if git -C "$repo" diff --cached --quiet -- "${paths[@]}"; then
        note "no commit needed"
        return 0
    fi
    git -C "$repo" commit --only \
        -m "$subject" \
        -m "$body" \
        -m "$COAUTHOR" \
        -- "${paths[@]}"
}

switch_or_create_target() {
    local label="$1"
    local repo="$2"
    local remote="$3"
    local target_branch="$4"
    local base_ref="$5"
    local required_anchor="$6"
    local current_branch current_head target_ref

    current_branch="$(git -C "$repo" branch --show-current)"
    current_head="$(git -C "$repo" rev-parse HEAD)"
    target_ref="$remote/$target_branch"

    if [[ "$current_branch" == "$target_branch" ]]; then
        ensure_ancestor "$repo" "$required_anchor" HEAD "$label current branch"
        return 0
    fi

    if ref_exists "$repo" "refs/heads/$target_branch"; then
        # Never abandon a detached/local commit by jumping to an unrelated
        # branch. The target must already contain the commit we are leaving.
        git -C "$repo" merge-base --is-ancestor "$current_head" "refs/heads/$target_branch" || \
            fail "$label local $target_branch does not contain current HEAD $current_head"
        git -C "$repo" switch "$target_branch"
        ensure_ancestor "$repo" "$required_anchor" HEAD "$label target branch"
        return 0
    fi

    if ref_exists "$repo" "$target_ref"; then
        git -C "$repo" merge-base --is-ancestor "$current_head" "$target_ref" || \
            fail "$label remote $target_ref does not contain current HEAD $current_head"
        git -C "$repo" switch --track -c "$target_branch" "$target_ref"
        ensure_ancestor "$repo" "$required_anchor" HEAD "$label target branch"
        return 0
    fi

    ensure_ancestor "$repo" "$required_anchor" "$base_ref" "$label base"
    git -C "$repo" switch -c "$target_branch" "$base_ref"
}

prepare_package() {
    local label="$1"
    local slug="$2"
    local repo="$3"
    local remote="$4"
    local base_branch="$5"
    local target_version="$6"
    local old_version="$7"
    local version_file="$8"
    local anchor="$9"
    local target_branch="dev/$target_version"
    local base_ref="$remote/$base_branch"
    local version

    echo
    echo "===== prepare $label $target_version ====="
    ensure_path_clean "$label" "$repo" "$version_file"
    switch_or_create_target "$label" "$repo" "$remote" "$target_branch" "$base_ref" "$anchor"

    version="$(read_version "$repo/$version_file")"
    if [[ "$version" == "$target_version" ]]; then
        note "__version__ already $target_version"
    elif [[ "$version" == "$old_version" ]]; then
        write_version "$repo/$version_file" "$target_version"
    else
        fail "$label has unexpected __version__=$version on $target_branch (expected $old_version or $target_version)"
    fi

    commit_paths_if_needed \
        "$repo" \
        "Bump version to $target_version" \
        "Prepare the development branch for the coordinated Loguru migration release." \
        "$version_file"
}

prepare_ibeis() {
    local remote="$1"
    local target_version=2.6.0
    local target_branch="dev/$target_version"
    local current_branch current_head main_ref version
    local version_file=ibeis/__init__.py
    local paths=(
        ibeis/__init__.py
        ibeis/gui/guiback.py
        dev/workspace/bump_dev_versions.sh
        dev/workspace/push_submodules.sh
        dev/workspace/pull_submodules.sh
        dev/workspace/workspace_status.sh
        dev/workspace/reconcile_loguru_release.sh
        tpl/utool
        tpl/vtool_ibeis
        tpl/dtool_ibeis
        tpl/guitool_ibeis
        tpl/plottool_ibeis
    )

    echo
    echo "===== prepare ibeis $target_version ====="
    ensure_path_clean "ibeis" "$ROOT" "$version_file"
    current_branch="$(git -C "$ROOT" branch --show-current)"
    current_head="$(git -C "$ROOT" rev-parse HEAD)"
    main_ref="$remote/main"

    ensure_ancestor "$ROOT" "$IBEIS_LOGURU_ANCHOR" "$main_ref" 'IBEIS main'
    ensure_ancestor "$ROOT" "$IBEIS_OLD_HOT_RELOAD_ANCHOR" "$remote/dev/2.5.1" 'IBEIS legacy dev/2.5.1'

    if [[ "$current_branch" == "$target_branch" ]]; then
        :
    elif [[ "$current_branch" == main ]]; then
        git -C "$ROOT" merge-base --is-ancestor "$main_ref" HEAD || \
            fail "Local IBEIS main is not a descendant of $main_ref; refusing to guess how to reconcile it"

        if ref_exists "$ROOT" "refs/heads/$target_branch" || ref_exists "$ROOT" "$remote/$target_branch"; then
            fail "$target_branch already exists while local main has work to preserve; reconcile that branch manually before rerunning"
        fi
        note "preserving local main HEAD ${current_head:0:12} as the base of $target_branch"
        git -C "$ROOT" switch -c "$target_branch"
    elif [[ -z "$current_branch" ]]; then
        [[ "$current_head" == "$(git -C "$ROOT" rev-parse "$main_ref")" ]] || \
            fail "Detached IBEIS HEAD is not exactly $main_ref; refusing to guess a base"
        git -C "$ROOT" switch -c "$target_branch" "$main_ref"
    else
        fail "IBEIS is on unexpected branch '$current_branch'; expected main or $target_branch"
    fi

    version="$(read_version "$ROOT/$version_file")"
    if [[ "$version" == "$target_version" ]]; then
        note "__version__ already $target_version"
    elif [[ "$version" == 2.5.0 ]]; then
        write_version "$ROOT/$version_file" "$target_version"
    else
        fail "IBEIS has unexpected __version__=$version (expected 2.5.0 or $target_version)"
    fi

    local stage_paths=()
    local path
    for path in "${paths[@]}"; do
        if [[ -e "$ROOT/$path" ]] || git -C "$ROOT" ls-files --error-unmatch -- "$path" >/dev/null 2>&1; then
            stage_paths+=("$path")
        fi
    done
    commit_paths_if_needed \
        "$ROOT" \
        "Prepare IBEIS $target_version development branch" \
        "Bump the application version, record the coordinated dependency branch commits, and retain the local workspace/logging follow-ups. The earlier dev/2.5.1 hot-reload branch is superseded by the Loguru migration already present on main." \
        "${stage_paths[@]}"
}

push_branch() {
    local label="$1"
    local repo="$2"
    local remote="$3"
    local expected_branch="$4"
    local branch
    branch="$(git -C "$repo" branch --show-current)"
    [[ "$branch" == "$expected_branch" ]] || fail "$label is on $branch, expected $expected_branch before push"
    echo "===== push $label $branch ====="
    git -C "$repo" push -u "$remote" "$branch"
    git -C "$repo" fetch "$remote" "$branch" --quiet
}

open_pr() {
    local slug="$1"
    local branch="$2"
    local version="$3"
    local extra_body="$4"
    local repo_full="$OWNER/$slug"
    local existing body_file
    local -a draft_flag=()

    existing="$(gh pr list --repo "$repo_full" --state open --base main --head "$branch" --json url --jq '.[0].url // ""')"
    if [[ -n "$existing" ]]; then
        echo "===== PR $repo_full ====="
        note "already open: $existing"
        return 0
    fi

    body_file="$(mktemp)"
    trap 'rm -f "$body_file"' RETURN
    cat > "$body_file" <<BODY
## Summary

Prepare the \`$branch\` development line for version $version as part of the coordinated IBEIS inject2-to-Loguru migration.

$extra_body

## Release coordination

This PR is intentionally part of a multi-repository release sequence. Dependency versions can be published in order before the final IBEIS dependency minimums are tightened.
BODY

    if [[ "$DRAFT_PRS" == 1 ]]; then
        draft_flag=(--draft)
    fi

    echo "===== create PR $repo_full:$branch -> main ====="
    gh pr create \
        --repo "$repo_full" \
        --base main \
        --head "$branch" \
        --title "Prepare $slug $version" \
        --body-file "$body_file" \
        "${draft_flag[@]}"
    rm -f "$body_file"
    trap - RETURN
}

print_relation() {
    local label="$1"
    local repo="$2"
    local main_ref="$3"
    local ahead behind
    read -r ahead behind < <(git -C "$repo" rev-list --left-right --count "HEAD...$main_ref")
    printf '  %-15s branch=%-12s version=%-7s main=+%s/-%s head=%s\n' \
        "$label" \
        "$(git -C "$repo" branch --show-current || true)" \
        "$4" \
        "$ahead" "$behind" \
        "$(git -C "$repo" rev-parse --short=10 HEAD)"
}

[[ -n "$ROOT" ]] || fail 'Could not determine the IBEIS repository root'
ensure_repo "$ROOT"
require_command git
require_command python
require_command gh

gh --version >/dev/null
gh auth status >/dev/null

# All managed repositories must be initialized before we change anything.
# Ambient tracked edits and untracked drafts are allowed. We stage only the
# explicit release paths below; Git itself will refuse a switch/merge if an
# ambient file would actually be overwritten.
ensure_repo "$ROOT/tpl/utool"
ensure_repo "$ROOT/tpl/vtool_ibeis"
ensure_repo "$ROOT/tpl/dtool_ibeis"
ensure_repo "$ROOT/tpl/guitool_ibeis"
ensure_repo "$ROOT/tpl/plottool_ibeis"


# Fetch first. No branch or commit is changed until every remote has been
# refreshed and all expected migration anchors can be verified.
fetch_repo utool "$ROOT/tpl/utool" utool UTOOL_REMOTE
fetch_repo vtool_ibeis "$ROOT/tpl/vtool_ibeis" vtool_ibeis VTOOL_REMOTE
fetch_repo dtool_ibeis "$ROOT/tpl/dtool_ibeis" dtool_ibeis DTOOL_REMOTE
fetch_repo guitool_ibeis "$ROOT/tpl/guitool_ibeis" guitool_ibeis GUITOOL_REMOTE
fetch_repo plottool_ibeis "$ROOT/tpl/plottool_ibeis" plottool_ibeis PLOTTOOL_REMOTE
fetch_repo ibeis "$ROOT" ibeis IBEIS_REMOTE

ensure_ancestor "$ROOT/tpl/utool" "$UTOOL_LOGURU_ANCHOR" "$UTOOL_REMOTE/dev/2.3.0" 'utool dev/2.3.0'
ensure_ancestor "$ROOT/tpl/vtool_ibeis" "$VTOOL_LOGURU_ANCHOR" "$VTOOL_REMOTE/main" 'vtool main'
ensure_ancestor "$ROOT/tpl/dtool_ibeis" "$DTOOL_LOGURU_ANCHOR" "$DTOOL_REMOTE/main" 'dtool main'
ensure_ancestor "$ROOT/tpl/guitool_ibeis" "$GUITOOL_LOGURU_ANCHOR" "$GUITOOL_REMOTE/main" 'guitool main'
ensure_ancestor "$ROOT/tpl/plottool_ibeis" "$PLOTTOOL_LOGURU_ANCHOR" "$PLOTTOOL_REMOTE/main" 'plottool main'
ensure_ancestor "$ROOT" "$IBEIS_LOGURU_ANCHOR" "$IBEIS_REMOTE/main" 'IBEIS main'
ensure_ancestor "$ROOT" "$IBEIS_OLD_HOT_RELOAD_ANCHOR" "$IBEIS_REMOTE/dev/2.5.1" 'IBEIS dev/2.5.1'

cat <<PLAN

Reconciliation plan
-------------------
  utool          -> dev/2.3.0 (continue existing Loguru branch; bump 2.2.2 -> 2.3.0)
  vtool_ibeis    -> dev/2.4.0 (branch from current remote main; bump 2.3.1 -> 2.4.0)
  dtool_ibeis    -> dev/1.2.0 (branch from current remote main; bump 1.1.2 -> 1.2.0)
  guitool_ibeis  -> dev/2.3.0 (branch from current remote main; bump 2.2.0 -> 2.3.0)
  plottool_ibeis -> dev/2.4.0 (branch from current remote main; bump 2.3.0 -> 2.4.0)
  ibeis          -> dev/2.6.0 (branch from local main so its unpushed commits are preserved)

  ibeis dev/2.5.1 is left untouched. Its hot-reload cleanup is superseded by
  the broader Loguru migration already on main; the new 2.6.0 branch is the
  forward release line.
PLAN

if [[ "$YES" != 1 ]]; then
    read -r -p 'Proceed with local branch/version commits, pushes, and draft PRs? [y/N] ' answer
    case "$answer" in
        y|Y|yes|YES) ;;
        *) echo 'Aborted.'; exit 0 ;;
    esac
fi

# Prepare all dependency commits locally first.
prepare_package utool utool "$ROOT/tpl/utool" "$UTOOL_REMOTE" dev/2.3.0 2.3.0 2.2.2 utool/__init__.py "$UTOOL_LOGURU_ANCHOR"
prepare_package vtool_ibeis vtool_ibeis "$ROOT/tpl/vtool_ibeis" "$VTOOL_REMOTE" main 2.4.0 2.3.1 vtool_ibeis/__init__.py "$VTOOL_LOGURU_ANCHOR"
prepare_package dtool_ibeis dtool_ibeis "$ROOT/tpl/dtool_ibeis" "$DTOOL_REMOTE" main 1.2.0 1.1.2 dtool_ibeis/__init__.py "$DTOOL_LOGURU_ANCHOR"
prepare_package guitool_ibeis guitool_ibeis "$ROOT/tpl/guitool_ibeis" "$GUITOOL_REMOTE" main 2.3.0 2.2.0 guitool_ibeis/__init__.py "$GUITOOL_LOGURU_ANCHOR"
prepare_package plottool_ibeis plottool_ibeis "$ROOT/tpl/plottool_ibeis" "$PLOTTOOL_REMOTE" main 2.4.0 2.3.0 plottool_ibeis/__init__.py "$PLOTTOOL_LOGURU_ANCHOR"

# Root last, after the submodule HEADs have moved to their version commits.
prepare_ibeis "$IBEIS_REMOTE"

# Push only after every local branch/commit has prepared successfully.
push_branch utool "$ROOT/tpl/utool" "$UTOOL_REMOTE" dev/2.3.0
push_branch vtool_ibeis "$ROOT/tpl/vtool_ibeis" "$VTOOL_REMOTE" dev/2.4.0
push_branch dtool_ibeis "$ROOT/tpl/dtool_ibeis" "$DTOOL_REMOTE" dev/1.2.0
push_branch guitool_ibeis "$ROOT/tpl/guitool_ibeis" "$GUITOOL_REMOTE" dev/2.3.0
push_branch plottool_ibeis "$ROOT/tpl/plottool_ibeis" "$PLOTTOOL_REMOTE" dev/2.4.0
push_branch ibeis "$ROOT" "$IBEIS_REMOTE" dev/2.6.0

if [[ "$CREATE_PRS" == 1 ]]; then
    open_pr utool dev/2.3.0 2.3.0 'This branch contains the utool Loguru/injection refactor plus the current release-workflow update.'
    open_pr vtool_ibeis dev/2.4.0 2.4.0 'The Loguru-related vtool cleanup is already on main; this branch establishes the next minor release line.'
    open_pr dtool_ibeis dev/1.2.0 1.2.0 'The dtool Loguru migration is already on main; this branch establishes the next minor release line.'
    open_pr guitool_ibeis dev/2.3.0 2.3.0 'The guitool Loguru migration is already on main; this branch establishes the next minor release line.'
    open_pr plottool_ibeis dev/2.4.0 2.4.0 'The plottool Loguru migration is already on main; this branch establishes the next minor release line.'
    open_pr ibeis dev/2.6.0 2.6.0 'This branch preserves the local post-migration IBEIS commits, records the coordinated dependency gitlinks, and supersedes the older dev/2.5.1 hot-reload-only branch.'
fi

echo
echo 'Final local release state:'
print_relation utool "$ROOT/tpl/utool" "$UTOOL_REMOTE/main" "$(read_version "$ROOT/tpl/utool/utool/__init__.py")"
print_relation vtool_ibeis "$ROOT/tpl/vtool_ibeis" "$VTOOL_REMOTE/main" "$(read_version "$ROOT/tpl/vtool_ibeis/vtool_ibeis/__init__.py")"
print_relation dtool_ibeis "$ROOT/tpl/dtool_ibeis" "$DTOOL_REMOTE/main" "$(read_version "$ROOT/tpl/dtool_ibeis/dtool_ibeis/__init__.py")"
print_relation guitool_ibeis "$ROOT/tpl/guitool_ibeis" "$GUITOOL_REMOTE/main" "$(read_version "$ROOT/tpl/guitool_ibeis/guitool_ibeis/__init__.py")"
print_relation plottool_ibeis "$ROOT/tpl/plottool_ibeis" "$PLOTTOOL_REMOTE/main" "$(read_version "$ROOT/tpl/plottool_ibeis/plottool_ibeis/__init__.py")"
print_relation ibeis "$ROOT" "$IBEIS_REMOTE/main" "$(read_version "$ROOT/ibeis/__init__.py")"

echo
echo 'The historical IBEIS dev/2.5.1 branch was not modified or merged.'
echo 'Review/close any old dev/2.5.1 PR manually after confirming the new dev/2.6.0 PR supersedes it.'
