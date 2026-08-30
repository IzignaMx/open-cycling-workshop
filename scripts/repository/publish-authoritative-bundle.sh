#!/usr/bin/env bash
set -euo pipefail

BUNDLE=${1:-}
REMOTE=${2:-git@github.com:IzignaMx/open-cycling-workshop.git}
MAIN_BRANCH=${OCWP_MAIN_BRANCH:-main}
BOOTSTRAP_BRANCH=${OCWP_BOOTSTRAP_BRANCH:-bootstrap/v0.1}

if [[ -z "$BUNDLE" || ! -f "$BUNDLE" ]]; then
  echo "Usage: $0 /path/to/repository.git.bundle [git-remote]" >&2
  exit 2
fi

for cmd in git sha256sum mktemp; do
  command -v "$cmd" >/dev/null || { echo "Missing required command: $cmd" >&2; exit 2; }
done

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

printf 'Bundle SHA-256: '
sha256sum "$BUNDLE" | tee "$TMP/bundle.sha256"
git bundle verify "$BUNDLE" >/dev/null

git clone --quiet "$BUNDLE" "$TMP/repo"
cd "$TMP/repo"

AUTHORITATIVE_HEAD=$(git rev-parse HEAD)
AUTHORITATIVE_TREE=$(git rev-parse 'HEAD^{tree}')
AUTHORITATIVE_COUNT=$(git ls-files | wc -l | tr -d ' ')

for required in \
  README.md \
  LICENSE \
  AGENTS.md \
  MANUAL-ACTIONS-CHECKLIST.md \
  docs/10-spec-development/execution-state.yaml \
  docs/10-spec-development/open-cycling-workshop-platform-agent-master-loop-v0.2.md \
  .github/workflows/ci.yml \
  .github/workflows/security.yml; do
  test -f "$required" || { echo "Authoritative bundle is missing $required" >&2; exit 3; }
done

git remote remove origin 2>/dev/null || true
git remote add target "$REMOTE"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
backup_branch() {
  local branch=$1
  local slug=${branch//\//-}
  if git ls-remote --exit-code --heads target "refs/heads/$branch" >/dev/null 2>&1; then
    git fetch --quiet target "refs/heads/$branch:refs/remotes/target/$slug"
    git push --quiet target "refs/remotes/target/$slug:refs/heads/pre-consolidation/${slug}-${STAMP}"
  fi
}

backup_branch "$MAIN_BRANCH"
backup_branch "$BOOTSTRAP_BRANCH"

# Explicitly replace the known incomplete destination with the authoritative bundle.
git push --force target "HEAD:refs/heads/$MAIN_BRANCH"
git push --force target "HEAD:refs/heads/$BOOTSTRAP_BRANCH"

REMOTE_MAIN=$(git ls-remote target "refs/heads/$MAIN_BRANCH" | awk '{print $1}')
REMOTE_BOOTSTRAP=$(git ls-remote target "refs/heads/$BOOTSTRAP_BRANCH" | awk '{print $1}')
[[ "$REMOTE_MAIN" == "$AUTHORITATIVE_HEAD" ]] || { echo "Remote main verification failed" >&2; exit 4; }
[[ "$REMOTE_BOOTSTRAP" == "$AUTHORITATIVE_HEAD" ]] || { echo "Remote bootstrap verification failed" >&2; exit 4; }

# Fetch back from the destination and verify both commit and tree, not only refs.
git fetch --quiet --force target "refs/heads/$MAIN_BRANCH:refs/remotes/verified/main"
VERIFIED_HEAD=$(git rev-parse refs/remotes/verified/main)
VERIFIED_TREE=$(git rev-parse 'refs/remotes/verified/main^{tree}')
[[ "$VERIFIED_HEAD" == "$AUTHORITATIVE_HEAD" ]] || { echo "Fetched commit mismatch" >&2; exit 5; }
[[ "$VERIFIED_TREE" == "$AUTHORITATIVE_TREE" ]] || { echo "Fetched tree mismatch" >&2; exit 5; }

printf 'Repository restore verified\n'
printf '  remote: %s\n' "$REMOTE"
printf '  head:   %s\n' "$AUTHORITATIVE_HEAD"
printf '  tree:   %s\n' "$AUTHORITATIVE_TREE"
printf '  files:  %s\n' "$AUTHORITATIVE_COUNT"
printf '  backup prefix: refs/heads/pre-consolidation/*-%s\n' "$STAMP"
