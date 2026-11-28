"""Offline theorem-output contract acceptance; author controls are not AI results."""
from contextlib import nullcontext
import inspect
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from maam import CorpusError, migration as mig, theorem_contract as contract
from maam.lean_sandbox import SandboxUnavailable


POSITIVE = [f"c0{i}" for i in range(1, 7)] + ["c01_fully_qualified_theorem"]
NEGATIVE = ["c01_def", "c01_wrong_goal", "c01_new_axiom", "c01_extra_import", "c01_proof_term"]


class TheoremContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="maam-theorem-contract-test-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.prepared = Path(cls.temporary.name) / "prepared"
        contract.prepare(cls.prepared, verify_commit=False)
        cls.completed = Path(cls.temporary.name) / "completed"
        shutil.copytree(cls.prepared, cls.completed)
        try:
            cls.checked = contract.run(cls.completed)
        except SandboxUnavailable as exc:
            raise unittest.SkipTest(str(exc)) from exc
        if cls.checked["status"] != "completed":
            raise AssertionError(cls.checked)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="maam-theorem-contract-case-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.output = self.folder / "completed"
        shutil.copytree(self.completed, self.output)

    def fresh(self):
        output = self.folder / "prepared"
        shutil.copytree(self.prepared, output)
        return output

    def test_real_sandbox_checks_all_twelve_expected_controls(self):
        state = contract.report(self.output)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["counts"], {"slots": 12, "completed": 12, "verified": 7, "rejected": 5})
        cases = {row["case_id"]: row for row in state["cases"]}
        self.assertEqual(set(cases), set(POSITIVE + NEGATIVE))
        for case in POSITIVE:
            self.assertEqual(cases[case]["status"], "verified", cases[case])
            self.assertTrue(cases[case]["matched"])
        for case in NEGATIVE:
            self.assertEqual(cases[case]["status"], "rejected", cases[case])
            self.assertTrue(cases[case]["matched"])
        self.assertTrue(cases["c01_def"]["proof_compiled"])
        self.assertIn("target is not a theorem", json.dumps(cases["c01_def"]["verification_failure"]))

    def test_offline_provenance_does_not_claim_model_calls_or_usage(self):
        state = contract.report(self.output)
        self.assertEqual(state["new_model_calls"], 0)
        self.assertEqual(state["provenance"], "offline_author_controls")
        self.assertIsNone(state["generation_usage"])
        for function in (contract.prepare, contract.task_input, contract.run, contract.report):
            parameters = inspect.signature(function).parameters
            self.assertNotIn("key_file", parameters)
            self.assertNotIn("transport", parameters)

    def test_preview_whitelist_has_explicit_theorem_contract_and_equal_mathematics(self):
        references = json.loads((self.output / "inputs/reference_proofs.json").read_text())["tasks"]
        for task in POSITIVE[:6]:
            with self.subTest(task=task):
                left = contract.task_input(self.output, task)
                right = contract.task_input(self.output, task, include_guide=True)
                self.assertEqual(right.pop("guide"), (self.output / "inputs/guide.txt").read_text())
                self.assertEqual(left, right)
                self.assertEqual(set(left), {"instructions", "lean_version", "sources", "target", "output_contract"})
                self.assertEqual(left["target"]["declaration"], "Submission.solve")
                self.assertEqual(left["target"]["kind"], "theorem")
                self.assertIn("theorem", left["instructions"])
                self.assertIn("theorem", left["output_contract"]["declaration_template"])
                self.assertIn("proof", json.dumps(left["output_contract"]["json_schema"]))
                self.assertTrue(all(set(row) == {"module", "content"} for row in left["sources"]))
                serialized = json.dumps(left)
                for forbidden in ("/home/", "reference_proofs.json", '"family"', '"bridge"', '"expected"'):
                    self.assertNotIn(forbidden, serialized)
                self.assertTrue(all(references[task]["proof"] not in row["content"] for row in left["sources"]))

    def test_unknown_task_does_not_return_a_payload(self):
        with self.assertRaises(CorpusError):
            contract.task_input(self.output, "c99")

    def test_preserved_json_source_is_submitted_without_declaration_rewriting(self):
        for case in POSITIVE + NEGATIVE:
            with self.subTest(case=case):
                folder = self.output / "attempts" / case
                response = json.loads((folder / "response.json").read_text())
                self.assertEqual((folder / "Proof.lean").read_bytes(), response["proof"].encode())
        source = (self.output / "attempts/c01_def/Proof.lean").read_text()
        self.assertRegex(source, r"\bdef\s+solve\b")
        self.assertNotRegex(source, r"\btheorem\s+solve\b")

    def test_replay_never_invokes_lean_or_resubmits_a_case(self):
        with (patch.object(contract, "probe") as probe,
              patch.object(contract, "lean_sandbox") as sandbox,
              patch.object(mig, "verify_attempt") as verify):
            self.assertEqual(contract.report(self.output), self.checked)
        probe.assert_not_called()
        sandbox.assert_not_called()
        verify.assert_not_called()

    def test_completed_run_cannot_be_repeated(self):
        with patch.object(mig, "verify_attempt") as verify:
            with self.assertRaises(CorpusError):
                contract.run(self.output)
        verify.assert_not_called()

    def test_changed_tool_fingerprint_rejects_replay(self):
        with patch.object(contract, "_hashes", return_value={}):
            with self.assertRaises(CorpusError):
                contract.report(self.output)

    def test_input_snapshots_cannot_be_changed_after_preparation(self):
        for name in ("protocol.json", "guide.txt", "reference_proofs.json"):
            with self.subTest(name=name):
                path = self.output / "inputs" / name
                original = path.read_bytes()
                path.write_bytes(original + b" ")
                try:
                    with self.assertRaises(CorpusError):
                        contract.report(self.output)
                finally:
                    path.write_bytes(original)

    def test_case_response_or_source_tampering_rejects_replay(self):
        for name in ("payload.json", "response.json", "Proof.lean", "verification.json"):
            with self.subTest(name=name):
                path = self.output / "attempts/c01" / name
                original = path.read_bytes()
                path.write_bytes(original + b" ")
                try:
                    with self.assertRaises(CorpusError):
                        contract.report(self.output)
                finally:
                    path.write_bytes(original)

    def test_removing_sandbox_evidence_cannot_keep_completed_controls_valid(self):
        (self.output / "sandbox.json").unlink()
        with self.assertRaises(CorpusError):
            contract.report(self.output)

    def test_same_stem_extra_reservation_filename_is_rejected(self):
        reservation = self.output / "reservations/c01.json"
        reservation.with_suffix(".txt").write_bytes(reservation.read_bytes())
        with self.assertRaises(CorpusError):
            contract.report(self.output)

    def test_command_log_tampering_rejects_replay(self):
        folder = self.output / "attempts/c01"
        result = json.loads((folder / "verification.json").read_text())
        log = folder / result["trace"][0]["logs"]["stdout"]["path"]
        log.write_bytes(log.read_bytes() + b"changed")
        with self.assertRaises(CorpusError):
            contract.report(self.output)

    def test_complete_source_limit_fails_before_sandbox_or_any_reservation(self):
        output = self.fresh()
        with (patch.object(contract, "MAX_SOURCE_BYTES", 1),
              patch.object(contract, "probe") as probe,
              patch.object(contract, "lean_sandbox") as sandbox,
              patch.object(mig, "verify_attempt") as verify):
            with self.assertRaises(CorpusError):
                contract.run(output)
        probe.assert_not_called()
        sandbox.assert_not_called()
        verify.assert_not_called()
        self.assertEqual(list((output / "reservations").iterdir()), [])
        self.assertEqual(contract.report(output)["counts"]["completed"], 0)

    def test_unavailable_sandbox_fails_without_case_reservation_or_verification(self):
        output = self.fresh()
        with (patch.object(contract, "probe", side_effect=SandboxUnavailable("synthetic unavailable")),
              patch.object(contract, "lean_sandbox") as sandbox,
              patch.object(mig, "verify_attempt") as verify):
            with self.assertRaisesRegex(SandboxUnavailable, "synthetic unavailable"):
                contract.run(output)
        sandbox.assert_not_called()
        verify.assert_not_called()
        self.assertEqual(list((output / "reservations").iterdir()), [])

    def test_interrupted_reserved_case_is_preserved_and_cannot_be_retried(self):
        output = self.fresh()
        with (patch.object(contract, "probe", return_value={"status": "synthetic-capability"}),
              patch.object(contract, "lean_sandbox", return_value=nullcontext("unused-lean")),
              patch.object(mig, "verify_attempt", side_effect=KeyboardInterrupt) as verify):
            with self.assertRaises(KeyboardInterrupt):
                contract.run(output)
            self.assertEqual(contract.report(output)["status"], "interrupted")
            self.assertTrue((output / "reservations/c01.json").exists())
            self.assertFalse((output / "attempts/c01/result.json").exists())
            with self.assertRaises(CorpusError):
                contract.run(output)
        self.assertEqual(verify.call_count, 1)

    def test_cli_exposes_no_key_file_or_live_next_action(self):
        script = Path(contract.__file__).resolve().parents[1] / "scripts/check_theorem_contract.py"
        result = subprocess.run([sys.executable, str(script), "--help"], capture_output=True,
                                text=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("prepare", result.stdout)
        self.assertNotIn("--key", result.stdout)
        self.assertNotIn("next", result.stdout)

    def test_negative_control_requires_its_expected_rejection_reason(self):
        failures = [
            ("rejected", "compile:Proof", "unrelated syntax error"),
            ("rejected", "audit", "unrelated audit error"),
            ("inconclusive", "toolchain", "environment unavailable"),
        ]
        for index, (status, stage, message) in enumerate(failures):
            with self.subTest(status=status, stage=stage):
                output = self.folder / f"wrong-reason-{index}"
                shutil.copytree(self.completed, output)
                for case in NEGATIVE:
                    shutil.rmtree(output / "attempts" / case)
                    (output / "reservations" / (case + ".json")).unlink()
                result = {"status": status, "trace": [], "audit": None,
                          "failure": {"kind": "verification_failed", "stage": stage,
                                      "message": message}}
                with (patch.object(contract, "lean_sandbox", return_value=nullcontext("unused-lean")),
                      patch.object(mig, "verify_attempt", return_value=result) as verify):
                    state = contract.run(output)
                verify.assert_called_once()
                self.assertEqual(state["status"], "failed")
                self.assertFalse(state["cases"][7]["matched"])
                self.assertEqual(len(list((output / "reservations").iterdir())), 8)


if __name__ == "__main__":
    unittest.main()
