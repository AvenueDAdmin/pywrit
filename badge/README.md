# Writ README badge

Show that your agent's writes are gated by Writ.

## Static badge (works today)

No API key, no signup. Same flat-badge design as the dynamic one, without the
live count:

```md
[![agent writes gated by Writ](https://cdn.jsdelivr.net/gh/withwrit/pywrit@main/badge/writ-gated.svg)](https://withwrit.com)
```

Preview:

![agent writes gated by Writ](writ-gated.svg)

## Dynamic badge (live count)

The dynamic badge renders your tenant's **live gated-write count over the
trailing 30 days**, computed from your Writ audit log — green when you've gated
at least one write in the window, grey at zero:

```md
[![agent writes gated by Writ](https://api.withwrit.com/v1/badge/writ_badge_YOUR_TOKEN.svg)](https://withwrit.com)
```

**Mint a token** (API key required — the token is minted against your tenant):

```bash
curl -s https://api.withwrit.com/v1/badge/tokens \
  -H "Authorization: Bearer writ_..." \
  -H "Content-Type: application/json" \
  -d '{"label": "my-agent repo"}'
```

The response includes `badgeUrl` and a ready-to-paste `markdown` snippet.
The `badgeToken` is shown exactly once — store it; you need it to revoke.

**Revoke** (the badge URL 404s immediately; embeds show a broken image, not a
stale claim):

```bash
curl -s https://api.withwrit.com/v1/badge/tokens/revoke \
  -H "Authorization: Bearer writ_..." \
  -H "Content-Type: application/json" \
  -d '{"badgeToken": "writ_badge_..."}'
```

> The dynamic badge endpoint ships with the gate. Until it's deployed,
> `POST /v1/badge/tokens` returns 404 — use the static badge above.

## What the badge proves (and doesn't)

**Proves:**

- Whoever embedded it controls a real Writ tenant (the token is minted with
  that tenant's API key).
- That tenant actually gates writes — the count comes live from the tenant's
  audit log. `0/30d` is reported honestly.

**Doesn't prove:**

- That the *specific repo* showing the badge is the codebase whose writes are
  gated. The badge binds a token to a tenant, not to a repo. Don't put it on a
  repo whose agent doesn't gate through Writ.

**Privacy:** the badge exposes only the aggregate 30-day count — no tenant
IDs, names, API keys, or receipt contents. The token itself is public by
design (it sits in your README); it cannot be used as an API key.

Full reference: [docs.withwrit.com/badge](https://docs.withwrit.com/badge).
