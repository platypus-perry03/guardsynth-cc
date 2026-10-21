import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.research_portal.artifact_registry import (
    ArtifactRegistryError,
    ArtifactRegistry,
    build_artifact_registry,
    classify_artifact_path,
)


ROOT = Path(__file__).resolve().parents[3]


class ArtifactRegistryTest(unittest.TestCase):
    def test_review_pages_share_canonical_assets_without_export_copies(self):
        from apps.research_portal import run as portal
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "PROJECT_REGISTRY.json").write_text(json.dumps({
                "projects": [{"id": "demo", "artifact_root": "projects/01-demo/artifacts"}],
                "platforms": [],
            }))
            run = root / "projects/01-demo/artifacts/restricted/review-001/run-001"
            run.mkdir(parents=True)
            (run / "RUN_MANIFEST.json").write_text('{"run_id":"run-001"}')
            source = run / "review.html"
            source.write_text('<html>Shared review</html>')
            entries = [{
                "id": name, "title": name, "description": "Review", "owner_id": "demo",
                "display_classification": "restricted", "artifact_classification": "restricted",
                "selector": {"run_label": "run-001"}, "asset_label": "review.html",
                "output_name": name + ".html",
            } for name in ("first", "second")]
            config = root / "registry.json"
            config.write_text(json.dumps({"schema_version": 1, "entries": entries}))
            before = set(root.rglob("*"))
            with patch.object(portal, "ROOT", root), patch.object(portal, "REVIEW_ASSET_REGISTRY", config):
                pages = portal._review_sources()
            self.assertEqual(pages[0]["href"], pages[1]["href"])
            self.assertEqual(set(root.rglob("*")), before)
            _, _, artifact_id, asset_id = pages[0]["href"].split("/")
            path, _ = ArtifactRegistry(root).resolve_asset(artifact_id, asset_id, include_restricted=True)
            self.assertEqual(path, source)

    def test_registry_discovers_owner_scoped_runs(self):
        records = build_artifact_registry(ROOT)

        guardsynth = [record for record in records if record["owner_id"] == "guardsynth-coc"]
        self.assertTrue(guardsynth)
        self.assertTrue(any(record["classification"] == "public" for record in guardsynth))
        self.assertTrue(all(record["classification"] in {"public", "restricted", "intermediate"} for record in guardsynth))
        self.assertTrue(any(
            asset["label"] == "IMAGE_ONLY_SCENE_REVIEW_WITH_IMAGES.html"
            for record in guardsynth for asset in record["assets"]
        ))
        self.assertNotIn("canonical_path", json.dumps(records))
        self.assertTrue(all(record["artifact_id"].startswith("art-") for record in records))

    def test_classification_is_derived_from_registered_owner_root(self):
        path = ROOT / "projects/04-guardsynth-coc/artifacts/restricted/example/RUN_MANIFEST.json"
        owner, classification = classify_artifact_path(ROOT, path)

        self.assertEqual(owner, "guardsynth-coc")
        self.assertEqual(classification, "restricted")

    def test_unregistered_artifact_path_is_rejected(self):
        with self.assertRaises(ArtifactRegistryError):
            classify_artifact_path(ROOT, ROOT / "projects/04-guardsynth-coc/STATUS.md")

    def test_asset_resolution_is_opaque_hash_bound_and_symlink_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "PROJECT_REGISTRY.json").write_text(
                json.dumps({"projects": [{"id": "demo", "path": "projects/01-demo", "artifact_root": "projects/01-demo/artifacts"}], "platforms": []}),
                encoding="utf-8",
            )
            run = root / "projects/01-demo/artifacts/restricted/demo-run-001/run-v1"
            run.mkdir(parents=True)
            (run / "RUN_MANIFEST.json").write_text(
                json.dumps({"experiment_id": "DEMO-001", "run_id": "run-v1"}), encoding="utf-8"
            )
            result = run / "RESULT.json"
            result.write_text('{"status":"PASS"}\n', encoding="utf-8")
            outside = root / "outside.json"
            outside.write_text('{"secret":true}\n', encoding="utf-8")
            (run / "leak.json").symlink_to(outside)

            registry = ArtifactRegistry(root)
            record = registry.records(include_restricted=True)[0]
            self.assertNotIn("canonical_path", json.dumps(record))
            self.assertNotIn("leak.json", {asset["label"] for asset in record["assets"]})
            asset = next(item for item in record["assets"] if item["label"] == "RESULT.json")
            path, media_type = registry.resolve_asset(
                record["artifact_id"], asset["asset_id"], include_restricted=True
            )
            self.assertEqual(path, result.resolve())
            self.assertEqual(media_type, "application/json; charset=utf-8")
            with self.assertRaises(ArtifactRegistryError):
                registry.detail(record["artifact_id"], include_restricted=False)

            result.write_text('{"status":"CHANGED"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ArtifactRegistryError, "hash changed"):
                registry.resolve_asset(record["artifact_id"], asset["asset_id"], include_restricted=True)


if __name__ == "__main__":
    unittest.main()
