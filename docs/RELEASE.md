# Releasing Writ's public packages

One release tag pushes everywhere. The whole flow:

```bash
# 1. Rehearse (changes nothing, publishes nothing):
./scripts/release.sh v1.2.3 --dry-run

# 2. Cut the release:
./scripts/release.sh v1.2.3
```

`scripts/release.sh vX.Y.Z` does the local half:

1. Validates the tag (`vX.Y.Z`) and that it doesn't already exist.
2. Stamps the version into every artifact's version file:
   `pyproject.toml` + `__init__.py` (`pywrit`), `mcp/pyproject.toml`
   (when the extraction lands), `npm/package.json` (when it lands).
3. Build-checks each package locally (skips gracefully if a build tool is missing).
4. Commits, tags (`git tag -a vX.Y.Z`), pushes the branch and the tag.

Pushing the tag triggers `.github/workflows/release.yml`, which does the
publish half:

1. **PyPI** — builds and uploads `pywrit` (and `writ-mcp` once it exists).
2. **npm** — publishes `writ-scan` (once it exists; `--access public`).
3. **GitHub Action tags** — force-moves `vX` and `vX.Y` to the new tag, so
   `uses: AvenueDAdmin/pywrit@v1` always tracks the latest `v1.x.y`.
   (GitHub Marketplace listing is automatic on release — no separate step.)
4. **Checklist issue** — opens a `release` issue from
   `.github/RELEASE_CHECKLIST.md` for the manual channels.

Artifacts that don't exist yet are auto-detected and skipped — the pipeline
covers them the moment they land, no workflow edits needed. Expected layout:

| Artifact       | Detected at                                              |
|----------------|----------------------------------------------------------|
| `pywrit`       | `./pyproject.toml`                                       |
| `writ-mcp`     | `mcp/pyproject.toml` (or `writ-mcp/pyproject.toml`)      |
| `writ-scan`    | `npm/package.json` (or `npm/writ-scan/package.json`)     |
| GitHub Action  | `action.yml`, `action/action.yml`, or `github-action/action.yml` |

## Secrets to configure (one time)

Repo settings → Settings → Secrets and variables → Actions → New repository secret:

| Secret           | Used by        | How to create it |
|------------------|----------------|------------------|
| `PYPI_API_TOKEN` | PyPI publish   | pypi.org → Account settings → API tokens → create a token scoped to the `pywrit` project (add `writ-mcp` scope once that project exists). Paste the whole token, including the `pypi-` prefix. |
| `NPM_TOKEN`      | npm publish    | npmjs.com → Access Tokens → Generate New Token → **Automation** type, with publish rights on `writ-scan`. |

`GITHUB_TOKEN` is provided automatically by Actions; the workflow's
`permissions` block (`contents: write`, `issues: write`) covers tag moves and
the checklist issue. Nothing else to configure.

Alternative (recommended long-term): PyPI [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) —
add this repo as a trusted publisher on each PyPI project and switch the
workflow from `twine` to `pypa/gh-action-pypi-publish`; then no long-lived
`PYPI_API_TOKEN` is needed at all.

The old `publish.yml` (PyPI-only, `TWINE_PASSWORD` secret) is superseded by
`release.yml`. Once `PYPI_API_TOKEN` is in place, the `TWINE_PASSWORD` secret
can be deleted.

## Manual steps per release (also in the auto-opened checklist issue)

- Bump the `writ-mcp` version in the Hermes **optional-mcps** catalog manifest.
- Update version on **MCP registry listings**.
- Update install/version references in the public **docs** (quickstart, changelog).
- Verify the new version renders on PyPI / npm.
- Announce only if approved (launch drafts live in the adoption package).

## Releasing from a branch

The script commits the version bump on your current branch and pushes both
the branch and the tag. Open a PR to merge the version-bump commit into
`main` afterwards — CI publishes from the tag either way.
