"""Frozen transfer assets and the boundary around development reference checks."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from maam import CorpusError
from scripts import check_transfer_tasks as check


class TransferTaskTests(unittest.TestCase):
    def test_v2_bytes_split_and_development_only_references(self):
        frozen, references = check.check_assets()
        self.assertEqual(frozen["package"]["package_id"], "hom-kernel-group-v2")
        self.assertEqual(set(references), {"d01", "d02", "d03", "d04"})

    def test_reserved_reference_is_rejected_before_any_lean(self):
        original = check.read_object
        def polluted(path):
            value = copy.deepcopy(original(path))
            if Path(path).name == "reference_proofs.json":
                value["tasks"]["r01"] = value["tasks"]["d01"]
            return value
        with patch.object(check, "read_object", side_effect=polluted):
            with self.assertRaisesRegex(CorpusError, "development references"):
                check.check_assets()

    def test_smoke_submits_no_reserved_goals_and_keeps_unmeasured_usage(self):
        seen = []
        def submit(session, value, **kwargs):
            seen.append((Path(session).name, value["task_id"]))
            return {"status": "verified"}
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "smoke"
            with patch.object(check, "compile_declarations", return_value=[]), \
                    patch.object(check, "submit_attempt", side_effect=submit):
                result = check.check(output)
            self.assertEqual(seen, [(condition, task) for condition in ("baseline", "treatment")
                                    for task in ("d01", "d02", "d03", "d04")])
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["reserved_solver_attempts"], 0)
            self.assertIn("not measured", result["generation_usage"])
            self.assertEqual(json.loads((output / "task-smoke-summary.json").read_text()), result)


if __name__ == "__main__":
    unittest.main()
