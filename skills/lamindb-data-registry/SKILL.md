---
name: lamindb-data-registry
description: "How to call LaminDBAgent's tools to read a LaminDB registry."
---

# Calling LaminDBAgent

This skill says how to call the LaminDBAgent extension's tools. For the method itself, use the BAAM skill `scientific-data-engineering`.

## Tools

- `lamindb_status`: shows which targets are configured, their routes and which settings are present. It never shows a value and makes no network call.
- `lamindb_get`: reads from a target. It sends `GET`, or `POST` on routes declared as reads, and is marked read only, so Biorouter's Smart approval runs it without asking.

## Targets

| Target | Base URL | Credential | Reads | Writes |
| --- | --- | --- | --- | --- |
| `hub` | `(set by you), or `LAMINDB_API_URL`` | `LAMINDB_API_KEY` (bearer) | GET `/**` | none |

## Rules

- Call `lamindb_status` first. It shows which targets are configured and which
  settings are missing, without showing any value.
- Pass `path` relative to the target's base URL, for example `/`. Put
  query values in `query`, not in the path.
- A full URL is accepted only on the target's own host. The extension refuses any
  other host, so do not try to reach other services through it.
- Never put a credential in a tool argument. The extension attaches it.
- This extension is read only: it has no write tool.
