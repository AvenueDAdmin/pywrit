# Release checklist: __VERSION__

Auto-opened by the release workflow. The tag `__VERSION__` already pushed
everywhere automated. These are the manual channels — check each box as done.

## Automated (done by CI)
- [x] Python packages published to PyPI (`pywrit`, plus `writ-mcp` if present)
- [x] npm package published (`writ-scan`, if present)
- [x] GitHub Action `vX` / `vX.Y` tags moved (if the Action exists in-repo)

## Manual channels
- [ ] **Hermes optional-mcps catalog** — bump the `writ-mcp` version in the
      optional-mcps catalog manifest (needs the public `writ-mcp` PyPI package)
- [ ] **MCP registry listings** — update version on MCP registry listings
      (e.g. mcp.so) to `__VERSION__`
- [ ] **Docs** — update install/version references in the public docs
      (quickstart, changelog). Docs ship with the release per repo convention.
- [ ] **Verify live artifacts** — confirm the new version renders on
      pypi.org/project/pywrit, pypi.org/project/writ-mcp (if applicable),
      and npmjs.com/package/writ-scan (if applicable)
- [ ] **Announce** — only with maintainer approval: post the launch/announcement
      drafts (Show HN, Reddit, etc.) from the adoption package
- [ ] Close this issue
