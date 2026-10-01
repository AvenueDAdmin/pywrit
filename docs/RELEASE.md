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
3. **Smithery** — builds a `.mcpb` bundle from `writ-mcp` and publishes it as
   `withwrit/writ-mcp`. Requires the `SMITHERY_API_KEY` repo secret.
4. **Official MCP Registry** — publishes `server.json` to
   `registry.modelcontextprotocol.io` using GitHub Actions OIDC.
5. **GitHub Action tags** — force-moves `vX` and `vX.Y` to the new tag, so
    `uses: withwrit/pywrit@v0` always tracks the latest `v0.x.y`.
   (GitHub Marketplace listing is automatic on release — no separate step.)
6. **Checklist issue** — opens a `release` issue from
    `.github/RELEASE_CHECKLIST.md` for the remaining manual or semi-automated channels.
7. **Catalog PRs** — `.github/workflows/mcp-catalog-prs.yml` opens/updates PRs
   against the Hermes optional-mcps catalog and punkpeye/awesome-mcp-servers
   with the new `writ-mcp` version. Requires the `CATALOG_PR_TOKEN` repo secret.

Artifacts that don't exist yet are auto-detected and skipped — the pipeline
covers them the moment they land, no workflow edits needed. Expected layout:

| Artifact       | Detected at                                              |
|----------------|----------------------------------------------------------|
| `pywrit`       | `./pyproject.toml`                                       |
| `writ-mcp`     | `mcp/pyproject.toml` (or `writ-mcp/pyproject.toml`)      |
| `writ-scan`    | `npm/package.json` (or `npm/writ-scan/package.json`)     |
| Smithery bundle| `.github/smithery/build_mcpb.py` + `mcp/pyproject.toml`   |
| GitHub Action  | `action.yml`, `action/action.yml`, or `github-action/action.yml` |

## Secrets to configure (one time)

Repo settings → Settings → Secrets and variables → Actions → New repository secret:

| Secret              | Used by           | How to create it |
|---------------------|-------------------|------------------|
| `PYPI_API_TOKEN`    | PyPI publish      | pypi.org → Account settings → API tokens → create a token scoped to **both** the `pywrit` and `writ-mcp` projects (or an account-scoped token). Paste the whole token, including the `pypi-` prefix. |
| `NPM_TOKEN`         | npm publish       | npmjs.com → Access Tokens → Generate New Token → **Automation** type, with publish rights on `writ-scan`. |
| `SMITHERY_API_KEY`  | Smithery publish  | smithery.ai → Account → API keys → create a key. The workflow publishes `withwrit/writ-mcp` from the built `.mcpb` bundle. |
| `CATALOG_PR_TOKEN`  | Catalog PRs       | GitHub personal access token (classic or fine-grained) with `repo` and `pull_requests:write` scopes for the target organizations (`NousResearch`, `punkpeye`). Used by `.github/workflows/mcp-catalog-prs.yml` to fork and open PRs. |

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

> Catalog PRs and registry publishing are now automated; the items below still
> need a human check or one-time action.

- **Hermes optional-mcps** — PR is opened automatically; verify it merged.
- **punkpeye/awesome-mcp-servers** — PR is opened automatically; verify it merged.
- **Official MCP Registry** — published automatically via OIDC; verify the new
  version is queryable at `registry.modelcontextprotocol.io`.
- **mcpservers.org** — one-time submission; the listing stays current via their
  scrape. Verify the badge is in the README.
- Update install/version references in the public **docs** (quickstart, changelog).
- Verify the new version renders on PyPI / npm / Smithery / MCP Registry.
- Announce only if approved (launch drafts live in the adoption package).

## Releasing from a branch

The script commits the version bump on your current branch and pushes both
the branch and the tag. Open a PR to merge the version-bump commit into
`main` afterwards — CI publishes from the tag either way.
