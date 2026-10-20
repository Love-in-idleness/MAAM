"""Local execution evidence over sealed searches; Lean results are explicit fixtures."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from maam import CorpusError
from maam import baseline_execution, baseline_methods, baseline_search
from maam.baseline import inventory_baseline
from maam.migration import (canonical, save_new, seal, start_session, submit_attempt,
                            task_request, unseal)
from maam.theory import digest


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "experiments/metered_transfer_v1/suite.json"


class BaselineExecutionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.tokens = 100
        self.verifier_status = "verified"
        self.verification_calls = 0
        self.verifier = patch("maam.migration.verify_attempt", side_effect=self.verify).start()
        self.network = patch("urllib.request.urlopen", side_effect=AssertionError(
            "No provider calls in deterministic local execution tests")).start()
        self.addCleanup(patch.stopall)

    def verify(self, frozen, request, source, artifact, **kwargs):
        self.verification_calls += 1
        if self.verifier_status == "interrupt":
            raise KeyboardInterrupt("fixture verification interruption")
        if self.verifier_status != "verified":
            return {"status": self.verifier_status, "trace": [], "audit": None,
                    "failure": {"kind": "fixture_failure", "message": self.verifier_status}}
        return {"status": "verified", "trace": [], "audit": {
            "targets": [{"name": "Submission.solve", "expected": request["task"]["goal"],
                         "goal_preserved": True, "proof_expr_nodes": 50}],
            "sources": [{"module": "Proof", "source_tokens": self.tokens}]}}

    def search(self, *, proof="by\n  have h := f x\n  rw [r] at h\n  exact h\n", name="search", methods=None,
               max_sweeps=1, stable_sweeps=1, tasks=("d01",)):
        seed = self.root / (name + "-seed")
        start_session(SUITE, seed, condition="baseline", solver_id="mocked-lean-fixture")
        self.tokens, self.verifier_status = 100, "verified"
        for task in tasks:
            request = task_request(seed, task)
            submit_attempt(seed, {"task_id": task, "request_sha256": request["request_sha256"],
                                  "proof": proof, "bridge": "Fixture only; Lean is mocked"})
        inventory = self.root / (name + "-inventory.json")
        inventory.write_text(json.dumps(inventory_baseline([seed], list(tasks))))
        policy = {"schema_version": 1, "methods": [
                      {"name": key, "instructions": value}
                      for key, value in baseline_methods.METHODS.items()] if methods is None else methods,
                  "max_sweeps": max_sweeps, "stable_sweeps": stable_sweeps,
                  "evidence_mode": "supplied_local"}
        search = self.root / name
        baseline_search.prepare_search(inventory, policy, search)
        return search

    def execution(self, **kwargs):
        search = self.search(**kwargs)
        output = self.root / (search.name + "-execution")
        baseline_execution.prepare_execution(search, output)
        return search, output

    def test_generated_candidate_is_bound_before_submission_and_only_shorter_proof_is_kept(self):
        search, output = self.execution()
        self.tokens = 50
        first = baseline_execution.execute_next(output)
        self.assertEqual(first["counts"]["candidates"], 1)
        self.assertEqual(first["counts"]["verified"], 1)
        self.assertEqual(first["counts"]["replacements"], 1)
        generated = unseal(output / "generated/0001.json")
        outcome = unseal(output / "outcomes/0001.json")
        self.assertEqual(generated["slot"], 1)
        self.assertEqual(generated["response"]["request_sha256"],
                         generated["request"]["request_sha256"])
        response, evidence = baseline_methods.generate(generated["request"])
        self.assertEqual(generated["response"], response)
        self.assertEqual(generated["evidence"], evidence)
        self.assertEqual(outcome["generated_sha256"],
                         digest((output / "generated/0001.json").read_bytes()))
        self.assertEqual(outcome["search_response_sha256"],
                         digest((search / "attempts/0001/response.json").read_bytes()))
        self.assertEqual(outcome["search_result_sha256"],
                         digest((search / "attempts/0001/result.json").read_bytes()))
        final = baseline_execution.execute_next(output)
        self.assertEqual(final["status"], "declared_methods_executed")
        self.assertEqual(final["counts"], {"scans": 2, "candidates": 1, "retains": 1,
            "verified": 1, "rejected": 0, "inconclusive": 0, "replacements": 1})
        self.assertEqual((final["initial_source_tokens"], final["selected_source_tokens"]), (100, 50))
        self.assertEqual(final, baseline_execution.report(output))

    def test_no_match_scans_never_call_lean_and_make_no_optimization_claim(self):
        _, output = self.execution(proof="by exact old_proof")
        before = self.verification_calls
        baseline_execution.execute_next(output)
        final = baseline_execution.execute_next(output)
        self.assertEqual(self.verification_calls, before)
        self.network.assert_not_called()
        self.assertEqual(final["counts"]["scans"], 2)
        self.assertEqual(final["counts"]["retains"], 2)
        self.assertIs(final["deterministic_methods_executed"], True)
        for flag in ("baseline_search_complete", "package_attribution_ready", "globally_shortest",
                     "model_search_verified", "definition_optimization_performed"):
            self.assertIs(final[flag], False)
        self.assertIsNone(final["generation_usage"])
        self.assertEqual(final["actual_provider_calls"], 0)
        self.assertEqual(final["selected_source_tokens"], 100)

    def test_verified_ties_and_rejected_candidates_never_replace_the_incumbent(self):
        for status in ("verified", "rejected"):
            with self.subTest(status=status):
                search, output = self.execution(name=status)
                self.tokens, self.verifier_status = 100, status
                result = baseline_execution.execute_next(output)
                self.assertEqual(result["counts"][status], 1)
                self.assertEqual(result["counts"]["replacements"], 0)
                self.assertEqual(result["selected_source_tokens"], 100)
                self.assertTrue((search / "attempts/0001/response.json").exists())
                self.assertTrue((output / "generated/0001.json").exists())
                final = baseline_execution.execute_next(output)
                self.assertEqual(final["counts"][status], 1)
                self.assertEqual(final["selected_source_tokens"], 100)

    def test_inconclusive_or_interrupted_verification_stops_without_retry(self):
        for status in ("inconclusive", "unknown_fixture_result", "interrupt"):
            with self.subTest(status=status):
                _, output = self.execution(name=status)
                self.verifier_status = status
                if status == "interrupt":
                    with self.assertRaises(KeyboardInterrupt):
                        baseline_execution.execute_next(output)
                else:
                    baseline_execution.execute_next(output)
                before = self.verification_calls
                report = baseline_execution.report(output)
                self.assertEqual(report["status"], "interrupted_or_inconclusive")
                self.assertFalse(report["deterministic_methods_executed"])
                self.assertEqual(report["selected_source_tokens"], 100)
                try:
                    baseline_execution.execute_next(output)
                except CorpusError:
                    pass
                self.assertEqual(self.verification_calls, before)
                self.assertEqual(len(list((output / "generated").glob("*.json"))), 1)

    def test_write_ahead_issuance_prevents_retry_at_every_interruption_boundary(self):
        for boundary in ("generation", "before_submit", "after_submit"):
            with self.subTest(boundary=boundary):
                _, output = self.execution(name=boundary)
                real_submit = baseline_search.submit
                def submitted_then_interrupted(*args, **kwargs):
                    real_submit(*args, **kwargs)
                    raise KeyboardInterrupt("fixture after durable submission")
                target = ("maam.baseline_methods.generate" if boundary == "generation"
                          else "maam.baseline_search.submit")
                effect = (submitted_then_interrupted if boundary == "after_submit"
                          else KeyboardInterrupt("fixture interruption"))
                with patch(target, side_effect=effect), self.assertRaises(KeyboardInterrupt):
                    baseline_execution.execute_next(output)
                rows = (output / "issued.jsonl").read_bytes().splitlines()
                self.assertEqual(len(rows), 2)
                self.assertEqual((output / "generated/0001.json").exists(), boundary != "generation")
                self.assertFalse((output / "outcomes/0001.json").exists())
                before = self.verification_calls
                self.assertEqual(baseline_execution.report(output)["status"],
                                 "interrupted_or_inconclusive")
                try:
                    baseline_execution.execute_next(output)
                except CorpusError:
                    pass
                self.assertEqual(self.verification_calls, before)
                self.assertEqual(len((output / "issued.jsonl").read_bytes().splitlines()), 2)

    def test_resealed_generation_or_outcome_tampering_is_rejected_before_verification(self):
        for field in ("request", "response", "evidence", "outcome"):
            with self.subTest(field=field):
                _, output = self.execution(name=field)
                baseline_execution.execute_next(output)
                path = output / ("outcomes/0001.json" if field == "outcome" else "generated/0001.json")
                record = unseal(path)
                if field == "request":
                    record["request"]["incumbent"]["proof"] += "\n-- fixture changed"
                elif field == "response":
                    record["response"]["proof"] += "\n-- fixture changed"
                elif field == "evidence":
                    record["evidence"]["after_proof_bytes"] += 1
                else:
                    record["search_result_sha256"] = "0" * 64
                path.write_bytes(canonical(seal(record)))
                if field != "outcome":
                    outcome_path = output / "outcomes/0001.json"
                    outcome = unseal(outcome_path)
                    outcome["generated_sha256"] = digest(path.read_bytes())
                    outcome_path.write_bytes(canonical(seal(outcome)))
                before = self.verification_calls
                with self.assertRaises(CorpusError):
                    baseline_execution.report(output)
                self.assertEqual(self.verification_calls, before)

    def test_changed_methods_tools_or_frozen_search_plan_are_rejected(self):
        search, output = self.execution()
        with patch.dict(baseline_methods.METHODS, {"simpa_local_hypothesis": "Changed fixture method"}):
            with self.assertRaises(CorpusError):
                baseline_execution.report(output)
        original_read = Path.read_bytes
        changed_tool = ROOT / "maam/baseline_methods.py"
        def changed_bytes(path):
            return original_read(path) + (b"\nchanged fixture\n" if path == changed_tool else b"")
        with patch.object(Path, "read_bytes", changed_bytes), self.assertRaises(CorpusError):
            baseline_execution.report(output)
        adapter_plan_path = output / "plan.json"
        original_plan = adapter_plan_path.read_bytes()
        original_journal = (output / "issued.jsonl").read_bytes()
        adapter_plan = unseal(adapter_plan_path)
        adapter_plan["max_scans"] = 0
        adapter_plan_path.write_bytes(canonical(seal(adapter_plan)))
        (output / "issued.jsonl").write_bytes(canonical(seal({
            "plan_sha256": digest(canonical(adapter_plan))})) + b"\n")
        with self.assertRaises(CorpusError):
            baseline_execution.report(output)
        adapter_plan_path.write_bytes(original_plan)
        (output / "issued.jsonl").write_bytes(original_journal)
        plan_path = search / "plan.json"
        plan = unseal(plan_path)
        plan["policy"]["methods"][0]["instructions"] = "Changed frozen search policy"
        plan_path.write_bytes(canonical(seal(plan)))
        with self.assertRaises(CorpusError):
            baseline_execution.report(output)

    def test_outside_adapter_submission_and_unissued_records_are_rejected(self):
        for stage in ("before", "after", "extra_record", "duplicate_issuance"):
            with self.subTest(stage=stage):
                search, output = self.execution(name=stage)
                if stage in {"after", "duplicate_issuance"}:
                    baseline_execution.execute_next(output)
                if stage == "extra_record":
                    save_new(output / "generated/0002.json", seal({"slot": 2}))
                elif stage == "duplicate_issuance":
                    journal = output / "issued.jsonl"
                    raw = journal.read_bytes()
                    journal.write_bytes(raw + raw.splitlines()[-1] + b"\n")
                else:
                    request = baseline_search.next_request(search)
                    response, _ = baseline_methods.generate(request)
                    baseline_search.submit(search, response)
                with self.assertRaises(CorpusError):
                    baseline_execution.report(output)

    def test_adapter_requires_fresh_small_search_and_exact_declared_methods(self):
        for index, options in enumerate((
            {"methods": [{"name": "unknown", "instructions": "Fixture"}]},
            {"methods": [{"name": "simpa_local_hypothesis", "instructions": "Changed"}]},
            {"max_sweeps": 2},
            {"tasks": ("d01", "d02", "d03", "d04")},
        )):
            with self.subTest(options=options):
                search = self.search(name="invalid" + str(index), **options)
                with self.assertRaises(CorpusError):
                    baseline_execution.prepare_execution(search, self.root / ("invalid-output" + str(index)))
        search = self.search(name="used")
        request = baseline_search.next_request(search)
        response, _ = baseline_methods.generate(request)
        baseline_search.submit(search, response)
        with self.assertRaises(CorpusError):
            baseline_execution.prepare_execution(search, self.root / "used-output")
        _, output = self.execution(name="existing")
        with self.assertRaises((CorpusError, FileExistsError)):
            baseline_execution.prepare_execution(search, output)


if __name__ == "__main__":
    unittest.main()
