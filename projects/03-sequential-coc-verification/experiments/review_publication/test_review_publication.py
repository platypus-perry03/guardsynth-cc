"""The export fails closed on identity-bearing and non-allowlisted material."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("review_publication", Path(__file__).with_name("run.py"))
API = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(API)
LABEL_SPEC = importlib.util.spec_from_file_location("agreement_replay", Path(__file__).with_name("agreement_replay.py"))
LABEL_API = importlib.util.module_from_spec(LABEL_SPEC)
LABEL_SPEC.loader.exec_module(LABEL_API)


class ReviewPublicationTests(unittest.TestCase):
    def test_authored_text_remains_unmodified(self):
        text = b"Stop until the pedestrian has passed. Proceed."
        API.scan(Path("evidence/controlled/cases.json"), text)

    def test_identity_in_content_rejected(self):
        for text in (b"LOCAL_PATH_REMOVED_34ac81463030", b"a.person@university.edu", b"github.com/author/repo", b"scene-0051"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                API.scan(Path("results.json"), text)

    def test_excluded_paths_and_binary_rejected(self):
        for name in ("restricted/cases.json", "data/cases.json", "paper/main.tex", "response-to-reviewer-1.json", "camera.mp4", "solver"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                API.scan(Path(name), b"{}")

    def test_remove_process_paths_preserves_predictions(self):
        record = {"command": ["LOCAL_PATH_REMOVED_982c4d9d9059"], "uppaal_run": {"executable": "LOCAL_PATH_REMOVED_982c4d9d9059"},
                  "expected": {"verdict": "UNKNOWN"}, "prediction": {"verdict": "CONTRADICTION", "first_event_id": "e1"}}
        self.assertEqual(API.strip_execution_paths(record), {"expected": record["expected"], "prediction": record["prediction"]})

    def test_anonymous_panel_rejects_notes_original_ids_and_free_text(self):
        header = ",".join(LABEL_API.HEADERS)
        valid_row = "G01,A,YES,STOP_OR_HOLD,TEXTUALLY_CONSISTENT"
        cases = [header + ",notes\n" + valid_row + ",private note\n",
                 header + "\n" + valid_row.replace("G01", "original_review_id") + "\n",
                 header + "\n" + valid_row.replace("STOP_OR_HOLD", "person wrote a sentence") + "\n"]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ratings.csv"
            for content in cases:
                with self.subTest(content=content), self.assertRaises(ValueError):
                    path.write_text(content)
                    LABEL_API.calculate(path, None, None)

    def test_anonymous_panel_rejects_incomplete_panel(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ratings.csv"
            path.write_text(",".join(LABEL_API.HEADERS) + "\nG01,A,YES,STOP_OR_HOLD,TEXTUALLY_CONSISTENT\n")
            with self.assertRaises(ValueError):
                LABEL_API.calculate(path, None, None)


if __name__ == "__main__":
    unittest.main()
