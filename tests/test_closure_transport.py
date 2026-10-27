"""Offline closure preparation: real Lean references and evidence-boundary checks."""
from contextlib import nullcontext
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from maam import CorpusError, closure_transport as closure
from maam import migration as mig
from maam.lean_sandbox import SandboxUnavailable


class ClosureTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="maam-closure-tests-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.folder = Path(cls.temporary.name)
        cls.prepared = cls.folder / "prepared"
        closure.prepare(cls.prepared, verify_commit=False)
        cls.completed = cls.folder / "completed"
        shutil.copytree(cls.prepared, cls.completed)
        try:
            cls.checked = closure.run(cls.completed)
        except SandboxUnavailable as exc:
            raise unittest.SkipTest(str(exc)) from exc
        if cls.checked["status"] != "completed":
            raise AssertionError(cls.checked)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="maam-closure-case-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.output = self.folder / "completed"
        shutil.copytree(self.completed, self.output)

    def fresh(self):
        output = self.folder / "prepared"
        shutil.copytree(self.prepared, output)
        return output

    def test_real_references_have_checked_map_contracts_without_model_claims(self):
        state = closure.report(self.output)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["counts"], {"tasks": 6, "verified": 6, "attempts": 6})
        self.assertEqual(state["new_model_calls"], 0)
        self.assertIsNone(state["generation_usage"])
        self.assertEqual(state["generation_mode"], "author_supplied_reference")
        self.assertFalse(state["evidence"]["ai_constructed_maps"])
        self.assertFalse(state["evidence"]["guide_effect_measured"])
        self.assertFalse(state["evidence"]["held_out_transfer"])
        positives = state["tasks"][:4]
        self.assertTrue(all(row["map_contract_verified"] for row in positives))
        self.assertEqual(sum(row["named_transport_dependency"] for row in positives), 4)
        self.assertTrue(all(not row["named_transport_dependency"] for row in state["tasks"][4:]))
        self.assertIsNotNone(state["compression"])

    def test_replay_recomputes_report_without_lean_or_resubmission(self):
        with (patch.object(closure, "probe") as probe,
              patch.object(closure, "lean_sandbox") as sandbox,
              patch.object(mig, "submit_attempt") as submit):
            self.assertEqual(closure.report(self.output), self.checked)
        probe.assert_not_called()
        sandbox.assert_not_called()
        submit.assert_not_called()

    def test_preview_whitelist_has_identical_mathematics_plus_optional_guide(self):
        left = closure.task_input(self.output, "c03")
        right = closure.task_input(self.output, "c03", include_guide=True)
        self.assertEqual(right.pop("guide"), (self.output / "inputs/guide.txt").read_text())
        self.assertEqual(left, right)
        self.assertEqual(set(left), {"lean_version", "sources", "target", "output_contract"})
        self.assertTrue(all(set(row) == {"module", "content"} for row in left["sources"]))
        serialized = json.dumps(left)
        for forbidden in ("reference_proofs", "bindings", "solver", "family", "condition", "/home/", "bridge"):
            self.assertNotIn(forbidden, serialized)
        self.assertIn("complete Proof.lean", left["output_contract"]["proof"])
        references = json.loads((self.output / "inputs/reference_proofs.json").read_text())["tasks"]
        self.assertNotIn(references["c03"]["proof"], serialized)

    def test_changed_tool_fingerprint_rejects_replay(self):
        with patch.object(closure, "_tools", return_value={}):
            with self.assertRaisesRegex(CorpusError, "controller changed"):
                closure.report(self.output)

    def test_changed_snapshot_source_rejects_replay(self):
        source = self.output / "math/snapshot/Products.lean"
        source.write_bytes(source.read_bytes() + b"\n-- changed\n")
        with self.assertRaisesRegex(CorpusError, "source fingerprint"):
            closure.report(self.output)

    def test_changed_guide_or_reference_rejects_replay(self):
        for name in ("guide.txt", "reference_proofs.json"):
            with self.subTest(name=name):
                target = self.output / "inputs" / name
                original = target.read_bytes()
                target.write_bytes(original + b" ")
                try:
                    with self.assertRaisesRegex(CorpusError, "reference or guide changed"):
                        closure.report(self.output)
                finally:
                    target.write_bytes(original)

    def test_reference_set_must_match_all_six_tasks_before_output_creation(self):
        for change in ("missing", "extra"):
            with self.subTest(change=change):
                fixture = self.folder / ("fixture-" + change)
                shutil.copytree(closure.FIXTURE, fixture)
                path = fixture / "reference_proofs.json"
                data = json.loads(path.read_text())
                if change == "missing":
                    data["tasks"].pop("c06")
                else:
                    data["tasks"]["unexpected"] = copy.deepcopy(data["tasks"]["c01"])
                path.write_text(json.dumps(data))
                output = self.folder / ("invalid-" + change)
                with self.assertRaisesRegex(CorpusError, "six tasks exactly"):
                    closure.prepare(output, fixture=fixture, verify_commit=False)
                self.assertFalse(output.exists())

    def test_submitted_complete_source_tampering_rejects_replay(self):
        source = self.output / "math/attempts/c01/001/Proof.lean"
        source.write_bytes(source.read_bytes() + b"\n-- changed\n")
        with self.assertRaisesRegex(CorpusError, "source.*fingerprint|source differs"):
            closure.report(self.output)

    def test_command_log_tampering_rejects_replay(self):
        attempt = self.output / "math/attempts/c01/001"
        result = mig.unseal(attempt / "result.json")
        log = attempt / result["trace"][0]["logs"]["stdout"]["path"]
        log.write_bytes(log.read_bytes() + b"changed")
        with self.assertRaisesRegex(CorpusError, "command log fingerprint"):
            closure.report(self.output)

    def test_complete_source_limit_checked_before_attempt_submission(self):
        fixture = self.folder / "small-proof-budget"
        shutil.copytree(closure.FIXTURE, fixture)
        refs = json.loads((fixture / "reference_proofs.json").read_text())["tasks"]
        path = fixture / "suite.json"
        suite = json.loads(path.read_text())
        suite["budget"]["max_proof_bytes"] = len(refs["c01"]["proof"].encode())
        path.write_text(json.dumps(suite))
        output = self.folder / "limited"
        closure.prepare(output, fixture=fixture, verify_commit=False)
        with (patch.object(closure, "probe", return_value={"status": "synthetic-capability"}),
              patch.object(closure, "lean_sandbox", return_value=nullcontext("unused-lean")),
              patch.object(mig, "submit_attempt") as submit):
            with self.assertRaisesRegex(CorpusError, "complete author proof"):
                closure.run(output)
        submit.assert_not_called()
        self.assertEqual(closure.report(output)["counts"]["attempts"], 0)

    def test_unavailable_sandbox_fails_closed_without_reference_submission(self):
        output = self.fresh()
        with (patch.object(closure, "probe", side_effect=SandboxUnavailable("synthetic unavailable")),
              patch.object(closure, "lean_sandbox") as sandbox,
              patch.object(mig, "submit_attempt") as submit):
            with self.assertRaisesRegex(SandboxUnavailable, "synthetic unavailable"):
                closure.run(output)
        sandbox.assert_not_called()
        submit.assert_not_called()
        self.assertFalse((output / "sandbox.json").exists())
        self.assertEqual(closure.report(output)["counts"]["attempts"], 0)

    def test_interrupted_reserved_reference_is_preserved_and_cannot_retry(self):
        output = self.fresh()
        with (patch.object(closure, "probe", return_value={"status": "synthetic-capability"}),
              patch.object(closure, "lean_sandbox", return_value=nullcontext("unused-lean")),
              patch.object(mig, "verify_attempt", side_effect=KeyboardInterrupt) as verify):
            with self.assertRaises(KeyboardInterrupt):
                closure.run(output)
            self.assertEqual(closure.report(output)["status"], "interrupted")
            self.assertTrue((output / "math/reservations/c01-001.json").exists())
            self.assertFalse((output / "math/attempts/c01/001/result.json").exists())
            with self.assertRaisesRegex(CorpusError, "no offline reference slot"):
                closure.run(output)
        self.assertEqual(verify.call_count, 1)


if __name__ == "__main__":
    unittest.main()
