# LaminDBAgent

Read a LaminDB instance's registry with the lamindb library: search and filter artifacts, collections, runs, features and labels, and describe a record with its lineage. Read only; your key goes only to Lamin.

Current version: **0.3.0**

This release adds read-only registry tools on `lamindb` 2.12.2 (Apache-2.0): `lamindb_instance`, `lamindb_search`, `lamindb_query` and `lamindb_describe`. lamindb connects to your instance itself; the extension keeps lamindb's settings in its own data folder (your `~/.lamin` is not read), hands it your key as `LAMIN_API_KEY` inside its own process, and never saves or deletes anything.

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
| `LAMINDB_DATA_DIR` | no | no | Optional folder for the extension's own lamindb settings. Default: a folder beside Biorouter's data, so your ~/.lamin is not used. |
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
