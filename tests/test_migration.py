"""Protocol invariants; actual Lean checks live in check_migration.py."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from maam import CorpusError
from maam.migration import (load_suite, start_session, task_request, submit_attempt,
                            session_report, compare_sessions, save_new, seal)

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "experiments/hom_kernel_migration/suite.json"


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def session(self, name="baseline", solver="same", mode="interactive_agent"):
        path = self.root / name
        start_session(SUITE, path, condition=name, solver_id=solver, mode=mode)
        return path

    def payload(self, session, task="d01"):
        request = task_request(session, task)
        return {"task_id": task, "request_sha256": request["request_sha256"],
                "proof": "by trivial", "bridge": "unit-test fixture"}

    def fake(self, status="verified", proof=40, package=80):
        def verify(frozen, request, source, artifact, **kwargs):
            if status != "verified":
                return {"status": status, "audit": None, "trace": [],
                        "failure": {"kind": "budget_exhausted", "stage": "compile", "message": "test timeout"}}
            target = {"name": "Submission.solve", "expected": request["task"]["goal"], "goal_preserved": True,
                      "proof_expr_nodes": 50, "source": {
                          "body_tokens": proof-10, "signature_tokens": 4, "declaration_tokens": proof-5}}
            sources = [{"module": "Proof", "source_tokens": proof}]
            if request["condition"] == "treatment":
                sources.append({"module": "Candidate", "source_tokens": package})
            return {"status": status, "trace": [], "audit": {"targets": [target], "sources": sources}}
        return verify

    def test_frozen_suite_and_pattern_split(self):
        frozen = load_suite(SUITE)
        tasks = frozen["manifest"]["tasks"]
        self.assertEqual(sum(t["split"] == "development" for t in tasks), 12)
        self.assertEqual(sum(t["split"] == "reserved" for t in tasks), 8)
        self.assertEqual(frozen["blobs"]["Candidate"], (ROOT/"experiments/hom_kernel/Candidate.lean").read_bytes())

    def test_task_request_contains_no_other_task_or_opposite_condition(self):
        baseline = self.session()
        req = task_request(baseline, "d01")
        self.assertEqual([s["module"] for s in req["sources"]], ["Base", "Tasks.D01"])
        self.assertNotIn("reserved", json.dumps(req))
        treatment = self.session("treatment")
        self.assertEqual([s["module"] for s in task_request(treatment,"d01")["sources"]],
                         ["Base", "Tasks.D01", "Candidate"])

    def test_cross_condition_replay_does_not_consume_a_slot(self):
        baseline, treatment = self.session(), self.session("treatment")
        with self.assertRaisesRegex(CorpusError, "different task, condition"):
            submit_attempt(treatment, self.payload(baseline))
        self.assertFalse((treatment/"attempts/d01").exists())

    def test_failure_and_interruption_consume_attempts(self):
        session = self.session()
        with patch("maam.migration.verify_attempt", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                submit_attempt(session, self.payload(session))
        with patch("maam.migration.verify_attempt", side_effect=self.fake("inconclusive")):
            for _ in range(2):
                submit_attempt(session, self.payload(session))
            with self.assertRaisesRegex(CorpusError, "attempt budget exhausted"):
                submit_attempt(session, self.payload(session))
        report = session_report(session)
        self.assertEqual([a["status"] for a in report["tasks"][0]["attempts"]],
                         ["incomplete", "inconclusive", "inconclusive"])
        self.assertEqual(report["tasks"][0]["status"], "not_observed_solved")
        self.assertFalse(report["training_eligible"])

    def test_empty_comparison_has_no_zero_cost_success_claim(self):
        before, after = self.session(), self.session("treatment")
        comparison = compare_sessions(before, after)
        self.assertIsNone(comparison["common_task_source_ledger"]["net_tokens_saved"])
        self.assertIsNone(comparison["common_task_source_ledger"]["package_tokens_charged_once"])

    def test_deleting_attempt_artifacts_does_not_restore_budget(self):
        session = self.session()
        with patch("maam.migration.verify_attempt", side_effect=self.fake("rejected")):
            for _ in range(3):
                result = submit_attempt(session, self.payload(session))
                shutil.rmtree(result["artifact"])
            with self.assertRaisesRegex(CorpusError, "budget exhausted"):
                submit_attempt(session, self.payload(session))
        self.assertEqual([a["status"] for a in session_report(session)["tasks"][0]["attempts"]],
                         ["incomplete"] * 3)

    def test_submission_cannot_replace_controller_fields(self):
        session = self.session()
        payload = self.payload(session)
        payload["goal"] = "True"
        with self.assertRaisesRegex(CorpusError, "controller-owned"):
            submit_attempt(session, payload)

    def test_full_package_charged_once_and_only_common_tasks_compared(self):
        before, after = self.session(), self.session("treatment")
        with patch("maam.migration.verify_attempt", side_effect=self.fake(proof=100)):
            for task in ("d01","d02","d03"):
                submit_attempt(before, self.payload(before,task))
        with patch("maam.migration.verify_attempt", side_effect=self.fake(proof=40,package=80)):
            for task in ("d01","d02"):
                submit_attempt(after, self.payload(after,task))
        c = compare_sessions(before, after)
        self.assertEqual(c["coverage"]["relation"], "baseline_superset")
        self.assertEqual(c["common_task_source_ledger"]["task_ids"], ["d01","d02"])
        self.assertEqual(c["common_task_source_ledger"]["net_tokens_saved"], 40)
        self.assertEqual(c["common_task_source_ledger"]["package_tokens_charged_once"], 80)

    def test_best_observed_attempt_is_selected_without_erasing_failures(self):
        session = self.session()
        for cost in (100,40):
            with patch("maam.migration.verify_attempt", side_effect=self.fake(proof=cost)):
                submit_attempt(session,self.payload(session))
        with patch("maam.migration.verify_attempt", side_effect=self.fake("rejected")):
            submit_attempt(session,self.payload(session))
        row=session_report(session)["tasks"][0]
        self.assertEqual(row["selected"]["attempt"],2)
        self.assertEqual(len(row["attempts"]),3)

    def test_mutated_snapshot_is_rejected(self):
        session = self.session()
        candidate = session/"snapshot/Candidate.lean"
        candidate.write_text(candidate.read_text()+"\n")
        with self.assertRaisesRegex(CorpusError,"fingerprint mismatch"):
            task_request(session,"d01")

    def test_tampered_attempt_and_config_are_detected(self):
        session = self.session()
        with patch("maam.migration.verify_attempt",side_effect=self.fake()):
            submit_attempt(session,self.payload(session))
        proof=session/"attempts/d01/001/Proof.lean"
        proof.write_text(proof.read_text()+"\n")
        with self.assertRaisesRegex(CorpusError,"fingerprint changed"):
            session_report(session)
        config=json.loads((session/"session.json").read_text())
        config["condition"]="treatment"
        (session/"session.json").write_text(json.dumps(config))
        with self.assertRaisesRegex(CorpusError,"record fingerprint mismatch"):
            task_request(session,"d01")

    def test_solver_identity_and_mode_must_match(self):
        before=self.session()
        after=self.session("treatment",solver="different")
        with self.assertRaisesRegex(CorpusError,"solver identity"):
            compare_sessions(before,after)

    def test_response_size_and_family_leakage_are_rejected(self):
        session=self.session()
        payload=self.payload(session)
        payload["proof"]="x"*32769
        with self.assertRaisesRegex(CorpusError,"response-size"):
            submit_attempt(session,payload)
        suite_folder=self.root/"bad-suite"
        shutil.copytree(SUITE.parent,suite_folder)
        data=json.loads((suite_folder/"suite.json").read_text())
        data["tasks"][-1]["family"]=data["tasks"][0]["family"]
        (suite_folder/"suite.json").write_text(json.dumps(data))
        with self.assertRaisesRegex(CorpusError,"crosses"):
            load_suite(suite_folder/"suite.json")


if __name__ == "__main__":
    unittest.main()
