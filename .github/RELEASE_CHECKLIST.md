# Release checklist: __VERSION__

Auto-opened by the release workflow. The tag `__VERSION__` already pushed
everywhere automated. These are the manual channels — check each box as done.

## Automated (done by CI)
- [x] Python packages published to PyPI (`pywrit`, plus `writ-mcp` if present)
- [x] npm package published (`writ-scan`, if present)
- [x] Smithery bundle published (`withwrit/writ-mcp`, if `mcp/` exists) —
      requires the `SMITHERY_API_KEY` repo secret; the job fails loudly if unset
- [x] GitHub Action `vX` / `vX.Y` tags moved (if the Action exists in-repo)
- [x] Catalog PRs opened — Hermes optional-mcps + punkpeye/awesome-mcp-servers
      (requires the `CATALOG_PR_TOKEN` repo secret; PRs need human merge)

## Manual channels / verification
- [ ] **Hermes optional-mcps catalog** — verify the auto-opened PR merged
- [ ] **punkpeye/awesome-mcp-servers** — verify the auto-opened PR merged
- [ ] **Official MCP Registry** — manually run `mcp-publisher publish` to update
      `io.github.AvenueDAdmin/writ` to `__VERSION__`
- [ ] **mcpservers.org** — one-time listing; verify badge is in the README
- [ ] **Docs** — update install/version references in the public docs
      (quickstart, changelog). Docs ship with the release per repo convention.
- [ ] **Verify live artifacts** — confirm the new version renders on
      pypi.org/project/pywrit, pypi.org/project/writ-mcp (if applicable),
      npmjs.com/package/writ-scan (if applicable), and smithery.ai/servers/withwrit/writ-mcp
- [ ] **Announce** — only with maintainer approval: post the launch/announcement
      drafts (Show HN, Reddit, etc.) from the adoption package
- [ ] Close this issue
