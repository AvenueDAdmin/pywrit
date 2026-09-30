#!/usr/bin/env bash
# Writ public-repo release script.
#
# One release tag pushes everywhere:
#   ./scripts/release.sh v1.2.3          # stamp, build-check, commit, tag, push
#   ./scripts/release.sh v1.2.3 --dry-run # full rehearsal; changes nothing, publishes nothing
#
# The script never publishes. Publishing happens in CI
# (.github/workflows/release.yml) when the tag is pushed.
#
# Artifacts are auto-detected; missing ones are skipped with a note:
#   - Python packages: ./pyproject.toml (pywrit), writ-mcp/pyproject.toml (writ-mcp)
#   - npm package:      npm/writ-scan/package.json (also writ-scan/package.json)
#   - GitHub Action:    action.yml, action/action.yml, or github-action/action.yml
#                       (tag versioning only; the tag IS the version)
#
set -euo pipefail

TAG=""
DRY_RUN=0
STAMP_ONLY=0
SKIP_PYPI=0
SKIP_NPM=0
SKIP_ACTION_TAGS=0
YES=0

usage() {
  cat <<'EOF'
Usage: scripts/release.sh vX.Y.Z [--dry-run] [--stamp-only] [--skip-pypi] [--skip-npm] [--skip-action-tags] [--yes]

  vX.Y.Z            Release tag, e.g. v1.2.3 (must not already exist)
  --dry-run         Rehearse everything in a throwaway worktree:
                    stamps versions, builds packages, prints every command
                    that would run — commits/tags/pushes nothing, publishes nothing
  --stamp-only      Stamp versions from the tag and verify, then exit.
                    No commit, tag, push, or publish. Used by CI.
  --skip-pypi       Do not build/publish Python packages
  --skip-npm        Do not build/publish the npm package
  --skip-action-tags
                    Do not move the vX / vX.Y Action tags
  --yes             Skip the confirmation prompt
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --stamp-only) STAMP_ONLY=1 ;;
    --skip-pypi) SKIP_PYPI=1 ;;
    --skip-npm) SKIP_NPM=1 ;;
    --skip-action-tags) SKIP_ACTION_TAGS=1 ;;
    --yes) YES=1 ;;
    -h|--help) usage; exit 0 ;;
    v*) TAG="$1" ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

[[ -n "$TAG" ]] || { echo "error: release tag required (e.g. v1.2.3)" >&2; usage; exit 1; }
[[ "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "error: tag must match vX.Y.Z (got '$TAG')" >&2; exit 1; }
VER="${TAG#v}"
MAJOR="${VER%%.*}"
MINOR="$(echo "$VER" | cut -d. -f1-2)"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

WORK="$REPO_ROOT"
cleanup() { :; }

if [[ "$DRY_RUN" == "1" ]]; then
  WORK="$(mktemp -d /tmp/pywrit-release-dryrun.XXXXXX)"
  echo "==> dry-run: rehearsing in throwaway worktree $WORK"
  git worktree add --detach "$WORK" HEAD >/dev/null
  cleanup() { git worktree remove --force "$WORK" >/dev/null 2>&1 || true; rm -rf "$WORK"; }
  trap cleanup EXIT
  cd "$WORK"
elif [[ "$STAMP_ONLY" == "0" ]]; then
  # Real run: the tree must be clean and the tag must be new.
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "error: working tree is not clean — commit or stash first" >&2
    exit 1
  fi
  if git ls-remote --tags origin "refs/tags/$TAG" | grep -q .; then
    echo "error: tag $TAG already exists on origin" >&2
    exit 1
  fi
fi

echo "==> release $TAG (version $VER)"

# ---------------------------------------------------------------- versions ---
stamp_pyproject() { # $1 = file, $2 = version
  python3 - "$1" "$2" <<'EOF'
import re, sys
path, ver = sys.argv[1], sys.argv[2]
src = open(path).read()
new, n = re.subn(r'^(version\s*=\s*")[^"]*(")', rf'\g<1>{ver}\g<2>', src, count=1, flags=re.M)
if n != 1:
    sys.exit(f"version field not found in {path}")
open(path, "w").write(new)
EOF
}

stamp_init_version() { # $1 = file, $2 = version
  python3 - "$1" "$2" <<'EOF'
import re, sys
path, ver = sys.argv[1], sys.argv[2]
src = open(path).read()
new, n = re.subn(r'(__version__\s*=\s*")[^"]*(")', rf'\g<1>{ver}\g<2>', src, count=1, flags=re.M)
if n != 1:
    sys.exit(f"__version__ not found in {path}")
open(path, "w").write(new)
EOF
}

PY_PKGS=()
if [[ -f "pyproject.toml" ]]; then PY_PKGS+=("."); fi
if [[ -f "writ-mcp/pyproject.toml" ]]; then PY_PKGS+=("writ-mcp"); fi

if [[ "$SKIP_PYPI" == "0" ]]; then
  for d in "${PY_PKGS[@]:-}"; do
    [[ -n "${d:-}" ]] || continue
    echo "--> stamping $d to $VER"
    stamp_pyproject "$d/pyproject.toml" "$VER"
    # stamp every __init__.py carrying __version__ under the package src tree
    while IFS= read -r init; do
      stamp_init_version "$init" "$VER"
    done < <(grep -rl '__version__' "$d/src" 2>/dev/null || true)
  done
  if [[ "${#PY_PKGS[@]}" -eq 0 ]]; then
    echo "--> no Python packages found (skipped)"
  fi
else
  echo "--> --skip-pypi: Python packages untouched"
fi

NPM_DIR=""
for cand in "npm/writ-scan" "writ-scan"; do
  if [[ -f "$cand/package.json" ]]; then NPM_DIR="$cand"; break; fi
done
if [[ "$SKIP_NPM" == "0" ]]; then
  if [[ -n "$NPM_DIR" ]]; then
    echo "--> stamping $NPM_DIR/package.json to $VER"
    python3 - "$NPM_DIR/package.json" "$VER" <<'EOF'
import json, sys
path, ver = sys.argv[1], sys.argv[2]
data = json.load(open(path))
data["version"] = ver
json.dump(data, open(path, "w"), indent=2)
open(path, "a").write("\n")
EOF
  else
    echo "--> no npm package found (looked in npm/writ-scan, writ-scan; skipped)"
  fi
else
  echo "--> --skip-npm: npm package untouched"
fi

ACTION_YML=""
for cand in "action.yml" "action/action.yml" "github-action/action.yml"; do
  if [[ -f "$cand" ]]; then ACTION_YML="$cand"; break; fi
done
if [[ -n "$ACTION_YML" ]]; then
  echo "--> GitHub Action found at $ACTION_YML (versioned by tag; nothing to stamp)"
else
  echo "--> no GitHub Action found (looked for action.yml at root, action/, github-action/; skipped)"
fi

# ------------------------------------------------- verify the stamp landed ---
echo "==> verifying stamped versions"
fail=0
check() { # $1 = file, $2 = expected version string
  if grep -q "\"$VER\"" "$1" 2>/dev/null || grep -q "'$VER'" "$1" 2>/dev/null; then
    echo "    ok: $1"
  else
    echo "    MISMATCH: $1 does not contain version $VER" >&2; fail=1
  fi
}
for d in "${PY_PKGS[@]:-}"; do
  [[ -n "${d:-}" ]] || continue
  check "$d/pyproject.toml" "$VER"
done
[[ -n "$NPM_DIR" ]] && check "$NPM_DIR/package.json" "$VER"
[[ "$fail" == "1" ]] && { echo "error: version stamp verification failed" >&2; exit 1; }

# ------------------------------------------------------------------- build ---
BUILD_OK=1
if [[ "$SKIP_PYPI" == "0" && "${#PY_PKGS[@]}" -gt 0 ]]; then
  if python3 -c "import build" 2>/dev/null; then
    rm -rf /tmp/pywrit-release-dist && mkdir -p /tmp/pywrit-release-dist
    for d in "${PY_PKGS[@]}"; do
      outdir="/tmp/pywrit-release-dist/${d//\//_}"
      echo "==> building Python package in $d"
      ( cd "$d" && python3 -m build --outdir "$outdir" )
      echo "    built: $(ls "$outdir" | tr '\n' ' ')"
    done
  else
    echo "==> 'python -m build' unavailable locally (pip install build); CI will build. Skipping local build check."
    BUILD_OK=0
  fi
fi

if [[ "$SKIP_NPM" == "0" && -n "$NPM_DIR" ]]; then
  if command -v npm >/dev/null 2>&1; then
    echo "==> npm pack --dry-run in $NPM_DIR"
    ( cd "$NPM_DIR" && npm pack --dry-run )
  else
    echo "==> npm not installed; CI will pack. Skipping local npm check."
    BUILD_OK=0
  fi
fi

if [[ -n "$ACTION_YML" ]]; then
  echo "==> validating $ACTION_YML"
  python3 - "$ACTION_YML" <<'EOF'
import sys
path = sys.argv[1]
src = open(path).read()
for key in ("name:", "description:", "runs:"):
    if key not in src:
        sys.exit(f"{path}: missing required key {key}")
print("    ok: action.yml has name/description/runs")
EOF
fi

if [[ "$DRY_RUN" == "1" ]]; then
  echo
  echo "==> DRY-RUN COMPLETE: no commits, no tags, no pushes, no publishes."
  echo "    Throwaway worktree will be removed; your repo is untouched."
  exit 0
fi

if [[ "$STAMP_ONLY" == "1" ]]; then
  echo
  echo "==> STAMP-ONLY COMPLETE: versions stamped from $TAG and verified. No commit/tag/push."
  exit 0
fi

echo
echo "==> planned git operations"
echo "    git add -A"
echo "    git commit -m \"release: $TAG\""
echo "    git tag -a $TAG -m \"Release $TAG\""
echo "    git push origin HEAD        # pushes the version-bump commit"
echo "    git push origin $TAG        # triggers .github/workflows/release.yml"
echo
echo "==> CI will then (per .github/workflows/release.yml)"
[[ "$SKIP_PYPI" == "0" ]] && echo "    - build + publish Python packages to PyPI (needs PYPI_API_TOKEN secret)"
[[ "$SKIP_NPM" == "0" ]] && echo "    - publish npm package to npm (needs NPM_TOKEN secret)"
[[ "$SKIP_ACTION_TAGS" == "0" ]] && echo "    - move v$MAJOR and v$MINOR tags to $TAG (GitHub Action versioning)"
echo "    - open a release-checklist issue for the manual steps"

if [[ "$YES" == "0" ]]; then
  read -r -p "Proceed with commit + tag + push for $TAG? [y/N] " ans
  [[ "$ans" =~ ^[Yy]$ ]] || { echo "aborted"; exit 1; }
fi

git add -A
git commit -m "release: $TAG"
git tag -a "$TAG" -m "Release $TAG"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
git push origin "$BRANCH"
git push origin "$TAG"

echo
echo "==> released $TAG. CI is publishing; watch it at:"
echo "    https://github.com/AvenueDAdmin/pywrit/actions"
echo "    Then merge the $BRANCH branch into main (open a PR) so the version bump lands."
