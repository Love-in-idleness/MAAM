"""Offline inventory controls with real sealed sessions and mocked Lean checks."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from maam import CorpusError
from maam.baseline import inventory_baseline
from maam.migration import start_session, submit_attempt, task_request
from maam.theory import digest

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "experiments/metered_transfer_v1/suite.json"


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tokens = 100
        self.verifier = patch("maam.migration.verify_attempt", side_effect=self.verify).start()
        self.addCleanup(patch.stopall)

    def verify(self, frozen, request, source, artifact, **kwargs):
        if "_reject_" in source:
            return {"status": "rejected", "trace": [], "audit": None,
                    "failure": {"kind": "verification_failed", "message": "fixture failure"}}
        return {"status": "verified", "trace": [], "audit": {
            "targets": [{"name": "Submission.solve", "expected": request["task"]["goal"],
                         "goal_preserved": True, "proof_expr_nodes": 50}],
            "sources": [{"module": "Proof", "source_tokens": self.tokens}]}}

    def session(self, name="one", suite=SUITE, condition="baseline"):
        path = self.root / name
        start_session(suite, path, condition=condition, solver_id="offline-test-fixture")
        return path

    def submit(self, root, tokens=100, proof="by trivial", task="d01"):
        self.tokens = tokens
        request = task_request(root, task)
        return submit_attempt(root, {"task_id": task, "request_sha256": request["request_sha256"],
                                     "proof": proof, "bridge": "fixture only"})

    def changed_suite(self, name, module=None, goal=False):
        folder = self.root / name
        shutil.copytree(SUITE.parent, folder)
        path = folder / "suite.json"
        value = json.loads(path.read_text())
        if module:
            source = folder / value["sources"][module]["path"]
            source.write_text(source.read_text() + "\n-- modified fixture\n")
            value["sources"][module]["sha256"] = digest(source.read_bytes())
        if goal:
            value["tasks"][0]["goal"] = "Tasks.different"
        path.write_text(json.dumps(value))
        return path

    def test_select_shorter_and_stable_session_ties(self):
        paths = [self.session(name) for name in ("first", "short", "tie")]
        for path, cost in zip(paths, (100, 50, 50)):
            self.submit(path, cost)
        result = inventory_baseline(paths, ["d01"])
        row = result["tasks"][0]
        self.assertEqual(row["selected"]["session_index"], 1)
        self.assertEqual(row["selected"]["proof_source_tokens"], 50)
        self.assertEqual(len(row["sessions"]), 3)
        selected = row["selected"]
        artifact = Path(selected["artifact"])
        self.assertEqual(selected["proof_sha256"], digest((artifact / "Proof.lean").read_bytes()))
        self.assertEqual(selected["result_sha256"], digest((artifact / "result.json").read_bytes()))

    def test_candidate_bytes_excluded_from_original_knowledge_identity(self):
        one = self.session()
        other = self.session("other", self.changed_suite("candidate-change", "Candidate"))
        self.submit(one)
        self.submit(other)
        a, b = (inventory_baseline([p], ["d01"]) for p in (one, other))
        self.assertEqual(a["knowledge_sha256"], b["knowledge_sha256"])
        combined = inventory_baseline([one, other], ["d01"])
        self.assertEqual(set(combined["knowledge"]["source_sha256"]), {"Base", "Tasks.D01"})
        self.assertEqual([s["module"] for s in combined["tasks"][0]["selected"]["original_import_context"]],
                         ["Base", "Tasks.D01"])

    def test_base_task_goal_and_axiom_changes_cannot_pool(self):
        one = self.session()
        for index, (module, goal) in enumerate((("Base", False), ("Tasks.D01", False), (None, True))):
            with self.subTest(module=module, goal=goal):
                suite = self.changed_suite("different" + str(index), module, goal)
                other = self.session("other" + str(index), suite)
                with self.assertRaisesRegex(CorpusError, "knowledge, goals or toolchain differ"):
                    inventory_baseline([one, other], ["d01"])
        suite = self.changed_suite("axioms")
        value = json.loads(suite.read_text())
        value["base"]["allowed_axioms"].append("badAxiom")
        suite.write_text(json.dumps(value))
        with self.assertRaises(CorpusError):
            self.session("bad-axioms", suite)

    def test_treatment_reserved_duplicates_and_large_scope_rejected(self):
        one = self.session()
        treatment = self.session("treatment", condition="treatment")
        with self.assertRaisesRegex(CorpusError, "only baseline"):
            inventory_baseline([treatment], ["d01"])
        for sessions, tasks in (([one, one], ["d01"]), ([one], ["r01"]),
                                ([one], ["d01", "d01"]), ([one], []),
                                ([one], ["d01", "d02", "d03", "d04", "r01"])):
            with self.subTest(tasks=tasks), self.assertRaises(CorpusError):
                inventory_baseline(sessions, tasks)

    def test_missing_failure_and_interruption_stay_visible(self):
        one = self.session()
        self.submit(one, proof="by _reject_")
        with patch("maam.migration.verify_attempt", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.submit(one)
        result = inventory_baseline([one], ["d01", "d02"])
        self.assertEqual(result["status"], "baseline_witnesses_missing")
        self.assertEqual(result["missing_tasks"], ["d01", "d02"])
        self.assertEqual([a["status"] for a in result["tasks"][0]["sessions"][0]["attempts"]],
                         ["rejected", "incomplete"])
        self.assertEqual(result["tasks"][1]["sessions"][0]["attempts"], [])

    def test_snapshot_and_seal_tampering_rejected(self):
        one = self.session()
        self.submit(one)
        path = one / "snapshot/Base.lean"
        content = path.read_bytes()
        path.write_bytes(content + b"\n")
        with self.assertRaises(CorpusError):
            inventory_baseline([one], ["d01"])
        path.write_bytes(content)
        seal = one / "session.json"
        value = json.loads(seal.read_text())
        value["solver"]["id"] = "tampered"
        seal.write_text(json.dumps(value))
        with self.assertRaises(CorpusError):
            inventory_baseline([one], ["d01"])

    def test_completed_and_interrupted_raw_proof_tampering_rejected(self):
        for name, interrupt in (("complete", False), ("interrupted", True)):
            one = self.session(name)
            if interrupt:
                with patch("maam.migration.verify_attempt", side_effect=KeyboardInterrupt):
                    with self.assertRaises(KeyboardInterrupt):
                        self.submit(one)
            else:
                self.submit(one)
            (one / "attempts/d01/001/Proof.lean").write_text("tampered")
            with self.subTest(name=name), self.assertRaises(CorpusError):
                inventory_baseline([one], ["d01"])

    def test_inventory_never_claims_search_readiness_or_zero_usage(self):
        one = self.session()
        self.submit(one)
        result = inventory_baseline([one], ["d01"])
        self.assertEqual(result["status"], "known_baseline_pool_frozen")
        for flag in ("baseline_search_complete", "package_attribution_ready", "globally_shortest",
                     "new_lean_verification_performed"):
            self.assertIs(result[flag], False)
        self.assertIsNone(result["generation_usage"])
        self.assertIsNone(result["sessions"][0]["generation_usage"])
        self.assertIn("maam/PackageCheck.lean", result["tool_sha256"])
        self.assertIn("scripts/lean_sandbox.py", result["tool_sha256"])

    def test_cli_writes_fresh_outputs_and_reports_missing_with_nonzero_status(self):
        spec = importlib.util.spec_from_file_location("prepare_baseline", ROOT / "scripts/prepare_baseline.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        one = self.session()
        output = self.root / "inventory.json"
        argv = ["--session", str(one), "--task", "d01", "--output", str(output)]
        self.assertEqual(cli.main(argv), 1)
        old = output.read_bytes()
        self.assertEqual(cli.main(argv), 2)
        self.assertEqual(output.read_bytes(), old)


if __name__ == "__main__":
    unittest.main()
