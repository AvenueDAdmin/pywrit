# writ-scan

Run the free Writ scanner on any repo with one command:

```bash
npx writ-scan .
```

It finds **ungated write sites** in your code — database writes, HTTP calls,
filesystem writes, SDK calls (Stripe, Prisma, ...), child processes — and maps
each one to a Writ verb so you can gate it with an allow/deny policy. Local,
deterministic, and free: it parses your code, makes no network calls, and needs
no API key.

- **JavaScript/TypeScript**: scanned with tree-sitter (scan-only; your files are
  never rewritten).
- **Python**: scanned with `ast`; `writ scan --apply` can insert gates with
  your approval.

## Requirements

- Node.js 18+
- Python 3.9+ (macOS and most Linux machines already have it; on Windows install
  from [python.org](https://www.python.org/downloads/) with "Add python.exe to PATH")

On first run the shim installs the `pywrit[polyglot]` Python package from PyPI
(one-time, ~30 seconds). Afterwards it starts instantly.

## Usage

```bash
npx writ-scan [path] [options]
```

| Option | What it does |
|---|---|
| `path` | Repo root to scan (default: current directory) |
| `--exclude SUBSTR` | Skip paths containing SUBSTR (repeatable) |
| `--policy-out FILE` | Where to write the discovered verb policy (default: `writ-policy.json`) |
| `--apply` | Write instrumentation into the repo (Python only; TS/JS is scan-only) |
| `--yes` | Apply without prompting |
| `--push-policy` | PUT the discovered policy to the Writ gate (needs `--key`) |

Example output:

```text
writ scan: /path/to/my-agent
  files scanned: 12  skipped: 0
  write sites: 7 in 5 function(s)
  gated: 0/7 (0%)
  verbs discovered: 4
    db.query
    http.post
    file.write
    stripe.create
```

It also prints a **risk report** (0-100, weighted by risk tier) and writes the
discovered verb policy to `writ-policy.json`.

## Environment variables

| Variable | Purpose |
|---|---|
| `WRIT_PYTHON` | Use an explicit Python interpreter instead of auto-detecting `python3` |
| `WRIT_PYWRIT_SPEC` | Override the pip spec installed on first run (default: `pywrit[polyglot]==<this version>`) |
| `WRIT_SCAN_NO_INSTALL` | Set to `1` to never `pip install`; fails with manual instructions instead |

Debug the shim itself with `npx writ-scan --writ-shim-info`.

## Versioning

`writ-scan` versions track `pywrit` releases one-to-one: `writ-scan@0.2.6`
wraps `pywrit==0.2.6`.

## Docs

Full CLI reference and gating recipes: https://github.com/AvenueDAdmin/pywrit#readme
and https://withwrit.com/docs
