---
name: lamindb-data-registry
description: "How to call LaminDBAgent's tools: read a LaminDB instance's artifacts, collections, runs, features and labels by search, filtered queries and descriptions."
---

# Calling LaminDBAgent

This skill says how to call the LaminDBAgent extension's tools. For the method itself (how to
organise data, features and lineage in a registry), use the BAAM skill `scientific-data-engineering`.

LaminDB is a data framework for biology: an instance holds a registry of artifacts (files and
tables with their storage paths), collections, transforms and runs (lineage), features, labels
(ULabel and Record), schemas and projects. The extension connects with the `lamindb` library to
the instance in `LAMINDB_INSTANCE` (`owner/name`), with the person's `LAMINDB_API_KEY` for a
LaminHub instance. Every tool only reads.

## Tools

- `lamindb_instance`: connects, and reports the instance, its storage root and how many records
  each registry holds. Start here.
- `lamindb_search`: LaminDB's ranked text search over one registry.
- `lamindb_query`: field filters over one registry, for example
  `{"key__startswith": "scrna/", "suffix": ".h5ad"}` on `Artifact`,
  `{"created_by__handle": "jane", "created_at__gte": "2026-01-01"}`, or `{"name__icontains": "pilot"}`
  on `ULabel`. Lookups: exact, iexact, contains, icontains, startswith, istartswith, endswith,
  iendswith, in, gt, gte, lt, lte, isnull. `fields` picks what to return (related fields with
  `__`, at most two hops); `order_by` sorts (`-created_at` by default).
- `lamindb_describe`: one record by uid (or a unique prefix): its fields and LaminDB's own
  description, which for an artifact includes features, labels, the storage path and the run
  that made it.
- `lamindb_status` and `lamindb_get` reach a LaminHub API address only if the person set
  `LAMINDB_API_URL` (a host under lamin.ai); most people do not need them.

## Rules

- To read an artifact's content, take its storage path from `lamindb_describe` and load it with
  the Developer shell (`lamindb` in a script), so the person sees the code.
- This extension never saves, deletes or moves anything in LaminDB. Changes go through the
  person's own scripts or LaminHub.
- Keep artifact uids, keys, versions, the run and transform that produced them, and the instance
  name in any report.
