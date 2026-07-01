# LaminDBAgent

BioRouter BRXT extension for LaminDB data registry workflows.

## What it provides
- MCP tools for status, target discovery, guarded API calls, guarded local command planning/execution, and JSON resource summarization.
- Read-first behavior: mutation-capable HTTP methods require `allow_mutation=true`.
- Local command execution is allowlisted and requires `allow_execute=true`.
- Bundled BioRouter skill: `lamindb-data-registry`.

## Install
Download `lamindbagent.brxt` from the release page and install it through BioRouter Extensions.

## License
Apache-2.0.
