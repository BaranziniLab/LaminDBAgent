# brxt-kit: allow-direct-network lamindb and lamindb-setup connect to the LaminDB instance named in LAMINDB_INSTANCE (LaminHub, the instance database and its storage) with the LAMINDB_API_KEY; nothing here takes a URL from the model
"""Typed, read-only LaminDB registry tools on the lamindb library (Apache-2.0).

LaminDB is a Python library over an instance database, not a REST API, so the 0.1.0 adapter's
lamin.ai/api target never answered. These tools connect to the instance in LAMINDB_INSTANCE
(owner/name) with lamindb and only read: search, filtered queries over named fields, and a
record's description. Nothing saves, deletes or moves data. lamindb keeps its settings in
LAMIN_SETTINGS_DIR, which this module points at the extension's own data folder before lamindb
is first imported, so your own ~/.lamin is neither read nor changed. The key is handed to
lamindb-setup as LAMIN_API_KEY inside this process only.
"""

import contextlib
import io
import json
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any, Optional, Union

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult
from mcp.types import TextContent, ToolAnnotations
from pydantic import Field

INSTANCE_ENV = "LAMINDB_INSTANCE"
KEY_ENV = "LAMINDB_API_KEY"
REGISTRIES = {"Artifact", "Collection", "Transform", "Run", "Record", "ULabel", "Feature", "Schema", "Project",
              "Reference", "Storage", "User", "Space", "Branch"}
LOOKUPS = {"exact", "iexact", "contains", "icontains", "startswith", "istartswith", "endswith", "iendswith",
           "in", "gt", "gte", "lt", "lte", "isnull"}
PART = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
INSTANCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
UID = re.compile(r"^[A-Za-z0-9]{4,32}$")
PREFERRED = ["uid", "key", "name", "handle", "description", "suffix", "size", "kind", "otype", "dtype", "type",
             "version_tag", "is_latest", "n_files", "n_observations", "root", "region", "started_at", "finished_at",
             "created_at", "updated_at"]
MAX_ROWS = 500
MAX_DESCRIBE_CHARS = 20000
ANSI = re.compile(r"\x1b\[[0-9;]*m")
_lock = threading.Lock()
_state: dict[str, Any] = {"connected": None}


def data_dir() -> Path:
    configured = (os.getenv("LAMINDB_DATA_DIR") or "").strip()
    if configured:
        return Path(configured).expanduser()
    root = (os.getenv("BIOROUTER_PATH_ROOT") or "").strip()
    if root:
        return Path(root).expanduser() / "data" / "extension-data" / "lamindbagent"
    if sys.platform == "win32":
        base = Path(os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "UCSF" / "biorouter" / "data"
    else:
        base = Path(os.getenv("XDG_DATA_HOME") or (Path.home() / ".local" / "share")) / "biorouter"
    return base / "extension-data" / "lamindbagent"


def _result(payload: Any) -> ToolResult:
    return ToolResult(content=[TextContent(type="text", text=json.dumps(payload, indent=2, ensure_ascii=False, default=str))])


def _ann(title: str) -> ToolAnnotations:
    return ToolAnnotations(title=title, readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)


def _redact(text: str) -> str:
    key = (os.getenv(KEY_ENV) or "").strip()
    return text.replace(key, "[REDACTED]") if key else text


def connect():
    """Import lamindb with its settings in our data folder and connect to LAMINDB_INSTANCE, once."""
    instance = (os.getenv(INSTANCE_ENV) or "").strip()
    if not instance:
        raise ToolError(f"{INSTANCE_ENV} is not set. Set it to your instance as owner/name in the extension's settings in Biorouter.")
    if not INSTANCE.fullmatch(instance):
        raise ToolError(f"{INSTANCE_ENV} must look like owner/name.")
    if _state["connected"] == instance:
        import lamindb as ln

        return ln
    if _state["connected"] is not None:
        raise ToolError(f"This extension is connected to {_state['connected']}; restart it to switch instances.")
    settings = data_dir() / "lamin-settings"
    settings.mkdir(parents=True, exist_ok=True)
    if "lamindb_setup" not in sys.modules:
        os.environ["LAMIN_SETTINGS_DIR"] = str(settings)
    key = (os.getenv(KEY_ENV) or "").strip()
    if key:
        os.environ["LAMIN_API_KEY"] = key
    os.environ.pop("LAMIN_CURRENT_INSTANCE", None)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        import lamindb_setup

        lamindb_setup.connect(instance)
        import lamindb as ln
    _state["connected"] = instance
    return ln


def registry(ln, name: str):
    if name not in REGISTRIES:
        raise ToolError(f"Unknown registry {name!r}. Registries: {', '.join(sorted(REGISTRIES))}.")
    model = getattr(ln, name, None)
    if model is None:
        raise ToolError(f"This lamindb has no {name} registry.")
    return model


def concrete_fields(model) -> list[str]:
    return [f.name for f in model._meta.concrete_fields if not f.name.startswith("_")]


def default_fields(model) -> list[str]:
    available = set(concrete_fields(model))
    return [f for f in PREFERRED if f in available]


def resolve_path(model, path: str, allow_lookup: bool) -> str:
    """Check a field path against the model: relation hops, then a field, then (for a filter) a lookup.

    Each part must be a real field of the model it is read on, so a name Django would read as some
    other lookup or transform (regex, year, unaccent) is refused rather than passed through."""
    parts = path.split("__")
    if allow_lookup and len(parts) > 1 and parts[-1] in LOOKUPS:
        parts = parts[:-1]
    if not parts or len(parts) > 3:
        raise ToolError(f"{path!r}: use a field, or related fields joined with __ (at most two hops).")
    current = model
    for index, name in enumerate(parts):
        if not PART.fullmatch(name):
            raise ToolError(f"{path!r}: {name!r} is not a field name.")
        try:
            field = current._meta.get_field(name)
        except Exception:
            raise ToolError(f"{path!r}: {current.__name__} has no field {name!r}. Fields: {', '.join(concrete_fields(current))}.") from None
        if index < len(parts) - 1:
            if not getattr(field, "is_relation", False) or field.related_model is None:
                raise ToolError(f"{path!r}: {name!r} is not a related field, so nothing can follow it.")
            current = field.related_model
    return path


def check_fields(model, fields: list[str]) -> list[str]:
    return [resolve_path(model, f, allow_lookup=False) for f in fields]


def check_filters(model, filters: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key, value in filters.items():
        resolve_path(model, key, allow_lookup=True)
        lookup = key.split("__")[-1] if key.split("__")[-1] in LOOKUPS else "exact"
        if lookup == "in":
            if not isinstance(value, list) or len(value) > MAX_ROWS or any(isinstance(v, (dict, list)) for v in value):
                raise ToolError(f"Filter {key!r} takes a list of at most {MAX_ROWS} plain values.")
        elif isinstance(value, (dict, list)):
            raise ToolError(f"Filter {key!r} takes a plain value.")
        out[key] = value
    return out


def _run(action):
    failure = None
    try:
        with _lock:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                ln = connect()
                payload = action(ln)
        return _result(payload)
    except ToolError as exc:
        failure = _redact(str(exc))
    except Exception as exc:
        failure = _redact(f"LaminDB could not answer ({type(exc).__name__}: {ANSI.sub('', str(exc))[:500]}).")
    raise ToolError(failure)


def register(mcp: FastMCP) -> None:
    def lamindb_instance() -> ToolResult:
        def action(ln):
            import lamindb_setup

            settings = lamindb_setup.settings.instance
            counts = {}
            for name in sorted(REGISTRIES):
                model = getattr(ln, name, None)
                if model is not None:
                    try:
                        counts[name] = model.filter().count()
                    except Exception:
                        counts[name] = None
            return {"instance": f"{settings.owner}/{settings.name}", "lamindb_version": getattr(ln, "__version__", None),
                    "storage_root": getattr(getattr(settings, "storage", None), "root_as_str", None),
                    "database": "postgresql" if getattr(settings, "dialect", "") == "postgresql" else getattr(settings, "dialect", None),
                    "registries": counts}
        return _run(action)

    mcp.tool(lamindb_instance, name="lamindb_instance",
             description="Connect to the LaminDB instance in LAMINDB_INSTANCE and report its name, storage root, lamindb version and the number of records in each registry.",
             annotations=_ann("LaminDB instance"))

    def lamindb_search(
        registry_name: str = Field(description="Artifact, Collection, Transform, Run, Record, ULabel, Feature, Schema, Project, Reference, Storage, User, Space or Branch."),
        text: str = Field(min_length=1, max_length=200, description="Words to search for."),
        fields: Optional[list[str]] = Field(default=None, max_length=30, description="Fields to return; sensible defaults when omitted."),
        limit: int = Field(default=20, ge=1, le=100),
    ) -> ToolResult:
        def action(ln):
            model = registry(ln, registry_name)
            cols = check_fields(model, fields) if fields else default_fields(model)
            rows = list(model.search(text, limit=limit).values(*cols))
            return {"registry": registry_name, "text": text, "returned": len(rows), "records": rows}
        return _run(action)

    mcp.tool(lamindb_search, name="lamindb_search",
             description="Search one LaminDB registry by text (LaminDB's own ranked search) and return the matching records' fields.",
             annotations=_ann("Search LaminDB"))

    def lamindb_query(
        registry_name: str = Field(description="Artifact, Collection, Transform, Run, Record, ULabel, Feature, Schema, Project, Reference, Storage, User, Space or Branch."),
        filters: Optional[dict[str, Any]] = Field(default=None, description="Django style filters, for example {\"key__startswith\": \"scrna/\", \"suffix\": \".h5ad\", \"created_by__handle\": \"jane\"}."),
        fields: Optional[list[str]] = Field(default=None, max_length=30, description="Fields to return, including related fields such as created_by__handle."),
        order_by: Optional[str] = Field(default="-created_at", max_length=80, description="A field to sort by, - for descending."),
        limit: int = Field(default=50, ge=1, le=MAX_ROWS),
    ) -> ToolResult:
        def action(ln):
            model = registry(ln, registry_name)
            cols = check_fields(model, fields) if fields else default_fields(model)
            query = model.filter(**check_filters(model, filters or {}))
            total = query.count()
            if order_by:
                check_fields(model, [order_by.lstrip("-")])
                query = query.order_by(order_by)
            rows = list(query.values(*cols)[:limit])
            return {"registry": registry_name, "filters": filters or {}, "matches": total, "returned": len(rows), "records": rows}
        return _run(action)

    mcp.tool(lamindb_query, name="lamindb_query",
             description=f"Query one LaminDB registry with field filters (exact, iexact, contains, icontains, startswith, in, gt, gte, lt, lte, isnull and more) and return up to {MAX_ROWS} records. Read only.",
             annotations=_ann("Query LaminDB"))

    def lamindb_describe(
        registry_name: str = Field(description="The record's registry, for example Artifact or Collection."),
        uid: str = Field(max_length=32, description="The record's uid (or a unique prefix of it)."),
    ) -> ToolResult:
        if not UID.fullmatch(uid):
            raise ToolError("uid is the record's LaminDB uid, letters and digits only.")

        def action(ln):
            model = registry(ln, registry_name)
            matches = list(model.filter(uid__startswith=uid)[:2])
            if not matches:
                raise ToolError(f"No {registry_name} has a uid starting with {uid}.")
            if len(matches) > 1:
                raise ToolError(f"Several {registry_name} records have a uid starting with {uid}; give more of it.")
            record = matches[0]
            text = ""
            describe = getattr(record, "describe", None)
            if describe is not None:
                try:
                    text = ANSI.sub("", describe(return_str=True) or "")
                except TypeError:
                    text = ""
            fields = model.filter(id=record.id).values(*default_fields(model)).first()
            return {"registry": registry_name, "fields": fields, "description": text[:MAX_DESCRIBE_CHARS],
                    "description_truncated": len(text) > MAX_DESCRIBE_CHARS}
        return _run(action)

    mcp.tool(lamindb_describe, name="lamindb_describe",
             description="Describe one LaminDB record by uid: its fields and LaminDB's own description (features, labels, storage path and lineage for an artifact).",
             annotations=_ann("Describe a LaminDB record"))
