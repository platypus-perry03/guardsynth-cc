"""A completed PEFT run's provenance exception must not admit future paths."""

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "projects/04-guardsynth-coc/artifacts/restricted/guardsynth-eblc-learning-001/"


class CheckpointNamingExceptionTest(unittest.TestCase):
    def test_superseded_checkpoint_exception_is_retired(self):
        catalog = json.loads((ROOT / "docs/architecture/NAMING_EXCEPTIONS.json").read_text())
        self.assertFalse(any("paper1-vlm-smoke" in item["pattern"] for item in catalog["exceptions"]))
        self.assertFalse((ROOT / (PREFIX + "paper1-vlm-smoke-2026-09-06-002")).exists())
        run = ROOT / (PREFIX + "paper1-vlm-smoke-2026-09-06-003")
        manifest = json.loads((run / "RUN_MANIFEST.json").read_text())
        for arm in ("l0", "l1", "l2", "l3"):
            self.assertTrue((run / "adapters" / arm).is_dir())
            self.assertIn(f"adapters/{arm}/adapter_model.safetensors", manifest["output_hashes"])


if __name__ == "__main__":
    unittest.main()
