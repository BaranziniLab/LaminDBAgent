"""LaminDB tools against a local SQLite instance made for the test (no network, anonymous user):
the read-only queries, input checks, and that lamindb's settings stay in the extension's folder."""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
TMP = Path(tempfile.mkdtemp(prefix="lamindbagent-test-"))
os.environ["LAMINDB_DATA_DIR"] = str(TMP / "data")
os.environ["LAMINDB_INSTANCE"] = "anonymous/testkb"
os.environ.pop("LAMIN_SETTINGS_DIR", None)

from fastmcp.exceptions import ToolError  # noqa: E402

from lamindbagent import lamindb_tools as lt  # noqa: E402

SETUP = textwrap.dedent(
    """
    import sys
    import pandas as pd
    import lamindb_setup
    lamindb_setup.init(storage=sys.argv[1])
    import lamindb as ln
    df = pd.DataFrame({"gene": ["EGFR", "TP53", "KRAS"], "score": [1.0, 2.0, 3.0]})
    ln.Artifact.from_dataframe(df, key="examples/genes.parquet", description="three genes").save()
    ln.Artifact.from_dataframe(df.head(1), key="examples/one_gene.parquet", description="one gene").save()
    ln.ULabel(name="pilot study").save()
    """
)


def setUpModule():
    settings = TMP / "data" / "lamin-settings"
    settings.mkdir(parents=True)
    env = {**os.environ, "LAMIN_SETTINGS_DIR": str(settings), "HOME": str(TMP / "home")}
    (TMP / "home").mkdir()
    subprocess.run([sys.executable, "-c", SETUP, str(TMP / "testkb")], env=env, check=True, capture_output=True, timeout=600)


def call(name, args=None):
    from fastmcp import Client

    from lamindbagent.server import create_server

    async def go():
        async with Client(create_server()) as client:
            return await client.call_tool(name, args or {}, raise_on_error=False)

    result = asyncio.run(go())
    return result.is_error, (result.content[0].text if result.is_error else json.loads(result.content[0].text))


class Checks(unittest.TestCase):
    """Runs after A_NoInstance (unittest orders classes by name), so it may connect."""

    @classmethod
    def setUpClass(cls):
        cls.artifact = lt.connect().Artifact

    def test_filters(self):
        model = self.artifact
        self.assertEqual(lt.check_filters(model, {"key__startswith": "a", "size__gt": 3, "created_by__handle": "x"}),
                         {"key__startswith": "a", "size__gt": 3, "created_by__handle": "x"})
        for bad in ({"_real_key": "x"}, {"key__regex": ".*"}, {"created_at__year": 2026}, {"Key": 1}, {"nope": 1},
                    {"created_by__handle__name__x": 1}, {"key__in": "x"}, {"key": {"a": 1}}, {"size__handle": 1}):
            with self.assertRaises(ToolError, msg=bad):
                lt.check_filters(model, bad)

    def test_fields(self):
        self.assertEqual(lt.check_fields(self.artifact, ["uid", "created_by__handle"]), ["uid", "created_by__handle"])
        for bad in ("__class__", "_real_key", "key__regex", "created_by__password"):
            with self.assertRaises(ToolError, msg=bad):
                lt.check_fields(self.artifact, [bad])


class Tools(unittest.TestCase):
    def test_instance(self):
        error, out = call("lamindb_instance")
        self.assertFalse(error, out)
        self.assertEqual(out["instance"], "anonymous/testkb")
        self.assertEqual(out["registries"]["Artifact"], 2)
        self.assertTrue((TMP / "data" / "lamin-settings" / ".lamin").is_dir())

    def test_query_search_describe(self):
        error, out = call("lamindb_query", {"registry_name": "Artifact", "filters": {"key__startswith": "examples/"}, "order_by": "key"})
        self.assertFalse(error, out)
        self.assertEqual([r["key"] for r in out["records"]], ["examples/genes.parquet", "examples/one_gene.parquet"])
        error, found = call("lamindb_search", {"registry_name": "Artifact", "text": "three genes"})
        self.assertFalse(error, found)
        self.assertEqual(found["records"][0]["key"], "examples/genes.parquet")
        uid = found["records"][0]["uid"]
        error, desc = call("lamindb_describe", {"registry_name": "Artifact", "uid": uid[:8]})
        self.assertFalse(error, desc)
        self.assertIn("examples/genes.parquet", desc["description"])
        self.assertEqual(desc["fields"]["uid"], uid)
        error, labels = call("lamindb_query", {"registry_name": "ULabel", "fields": ["uid", "name"]})
        self.assertEqual([r["name"] for r in labels["records"]], ["pilot study"])

    def test_refusals(self):
        self.assertTrue(call("lamindb_query", {"registry_name": "Secrets"})[0])
        self.assertTrue(call("lamindb_query", {"registry_name": "Artifact", "fields": ["_real_key"]})[0])
        self.assertTrue(call("lamindb_describe", {"registry_name": "Artifact", "uid": "../x"})[0])

    def test_annotations_are_read_only(self):
        from fastmcp import Client

        from lamindbagent.server import create_server

        async def go():
            async with Client(create_server()) as client:
                return {t.name: t.annotations.model_dump(by_alias=True) for t in await client.list_tools()}

        for name, hints in asyncio.run(go()).items():
            if name != "lamindb_write":
                self.assertTrue(hints["readOnlyHint"], name)


class A_NoInstance(unittest.TestCase):
    """Runs first (unittest orders classes by name), while nothing is connected yet."""

    def test_missing_instance_is_explained(self):
        saved = os.environ.pop("LAMINDB_INSTANCE")
        try:
            with self.assertRaises(ToolError) as caught:
                lt.connect()
            self.assertIn("LAMINDB_INSTANCE is not set", str(caught.exception))
        finally:
            os.environ["LAMINDB_INSTANCE"] = saved


if __name__ == "__main__":
    unittest.main()
