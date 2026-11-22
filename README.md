# LaminDBAgent

Security release for LaminDB access: your LaminDB key now goes only to a lamin.ai address you set. The lamin.ai/api address the 0.1.0 release used no longer exists; registry tools on the lamindb library arrive in 0.3.0.

Current version: **0.2.0**

The 0.1.0 adapter sent your LaminDB key to any URL the model named, and its default `https://lamin.ai/api` answers 404. This release binds the key to a LaminHub address you set (a host under `lamin.ai`) and removes the dead default and the command runner. Registry tools on the `lamindb` library arrive in 0.3.0.

This is a Biorouter extension (a `.brxt` bundle) built on the BRXT adapter kit
1.0.1. Install it from BAAM in Biorouter, or from a file:

```bash
biorouter extension install dist/lamindbagent.brxt
```

## Tools

- `lamindb_status`: shows which targets are configured, their routes and which settings are present. It never shows a value and makes no network call.
- `lamindb_get`: reads from a target. It sends `GET`, or `POST` on routes declared as reads, and is marked read only, so Biorouter's Smart approval runs it without asking.

## Targets

| Target | Base URL | Credential | Reads | Writes |
| --- | --- | --- | --- | --- |
| `hub` | `(set by you), or `LAMINDB_API_URL`` | `LAMINDB_API_KEY` (bearer) | GET `/**` | none |

## Settings

| Variable | Required | Secret | Purpose |
| --- | --- | --- | --- |
| `LAMINDB_INSTANCE` | no | no | Your LaminDB instance as owner/name |
| `LAMINDB_API_URL` | no | no | Optional LaminHub API base URL (https, a host under lamin.ai). Leave empty unless LaminHub support gave you one. |
| `LAMINDB_API_KEY` | no | yes | LaminDB API key from lamin.ai, sent only to lamin.ai hosts |
| `LAMINDB_LOG_LEVEL` | no | no | Logging level |

## How it protects your credentials

- Each credential is attached only to requests for its own target's host. A full URL
  that names another host, a path starting with `//`, plain `http` and a redirect to
  another host are all refused, so a prompt that names a URL cannot move a key off
  the service it belongs to.
- Reads use `GET`, or `POST` on the routes declared as reads. Writes go through a
  separate tool that Biorouter asks you to approve every time, and only to declared
  routes.
- The extension never runs a local command. Use Biorouter's Developer shell for that.
- Credential values never appear in tool results, error messages or logs.

## Develop and release

```bash
uv sync
uv run python -m unittest discover -s tests -v   # contract tests and leak suite
uv run python scripts/build_brxt.py               # writes dist/lamindbagent.brxt and SHA256SUMS
uv run python scripts/version.py X.Y.Z            # moves every version string together
```

Push a tag `vX.Y.Z` equal to the manifest version to publish a release. The release
workflow refuses any other tag. Do not edit `src/lamindbagent/_kit/` or `tests/kit_testing/`:
they are vendored from the kit in the Biorouter repository
(`scripts/brxt-adapter-kit/`, documented in `docs/extensions/brxt-adapter-kit.md`).

## License

Apache-2.0. See `LICENSE` and `NOTICE`.
