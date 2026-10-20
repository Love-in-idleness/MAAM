"""Bounded search controls using sealed sessions and explicitly mocked Lean evidence."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from maam import CorpusError
from maam import baseline_search
from maam.baseline import inventory_baseline
from maam.migration import canonical, save_new, seal, start_session, submit_attempt, task_request
from maam.theory import digest


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "experiments/metered_transfer_v1/suite.json"


class BaselineSearchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.tokens = 100
        self.verification_calls = 0
        self.verifier = patch("maam.migration.verify_attempt", side_effect=self.verify).start()
        patch("urllib.request.urlopen", side_effect=AssertionError("No network in local search tests")).start()
        self.addCleanup(patch.stopall)

    def verify(self, frozen, request, source, artifact, **kwargs):
        self.verification_calls += 1
        if "_interrupt_fixture_" in source:
            raise KeyboardInterrupt("fixture interruption")
        for marker, status in (("_reject_fixture_", "rejected"),
                               ("_inconclusive_fixture_", "inconclusive")):
            if marker in source:
                return {"status": status, "trace": [], "audit": None,
                        "failure": {"kind": "fixture_failure", "message": marker}}
        return {"status": "verified", "trace": [], "audit": {
            "targets": [{"name": "Submission.solve", "expected": request["task"]["goal"],
                         "goal_preserved": True, "proof_expr_nodes": 50}],
            "sources": [{"module": "Proof", "source_tokens": self.tokens}]}}

    def prepare(self, *, tasks=("d01",), methods=1, max_sweeps=2, stable_sweeps=1,
                name="search"):
        seed = self.root / (name + "-seed")
        start_session(SUITE, seed, condition="baseline", solver_id="mocked-lean-fixture")
        self.tokens = 100
        for task in tasks:
            request = task_request(seed, task)
            submit_attempt(seed, {"task_id": task, "request_sha256": request["request_sha256"],
                                  "proof": "by _seed_fixture_", "bridge": "Fixture only"})
        inventory = self.root / (name + "-inventory.json")
        inventory.write_text(json.dumps(inventory_baseline([seed], list(tasks))))
        policy = {"schema_version": 1,
                  "methods": [{"name": "method" + str(i), "instructions": "Fixture local review"}
                              for i in range(methods)],
                  "max_sweeps": max_sweeps, "stable_sweeps": stable_sweeps,
                  "evidence_mode": "supplied_local"}
        search = self.root / name
        baseline_search.prepare_search(inventory, policy, search)
        return search, inventory, policy, seed

    def candidate(self, search, *, cost=50, proof="by _candidate_fixture_"):
        self.tokens = cost
        request = baseline_search.next_request(search)
        self.assertIsNotNone(request)
        return baseline_search.submit(search, {"action": "candidate",
            "request_sha256": request["request_sha256"], "proof": proof, "bridge": "Fixture only"})

    def retain(self, search):
        request = baseline_search.next_request(search)
        self.assertIsNotNone(request)
        return baseline_search.submit(search, {"action": "retain",
            "request_sha256": request["request_sha256"], "reason": "No shorter fixture found"})

    def test_only_a_strictly_shorter_certificate_replaces_the_incumbent(self):
        search, *_ = self.prepare(methods=3)
        first = baseline_search.next_request(search)["incumbent"]
        self.assertEqual(first["proof_source_tokens"], 100)
        self.candidate(search, cost=50, proof="by _first_shorter_fixture_")
        shorter = baseline_search.next_request(search)["incumbent"]
        self.assertEqual(shorter["proof_source_tokens"], 50)
        self.candidate(search, cost=50, proof="by _tied_fixture_")
        self.assertEqual(baseline_search.next_request(search)["incumbent"], shorter)
        result = self.candidate(search, cost=90, proof="by _longer_fixture_")
        self.assertEqual(result["initial_source_tokens"], 100)
        self.assertEqual(result["selected_source_tokens"], 50)
        self.assertEqual(baseline_search.next_request(search)["incumbent"], shorter)

    def test_retain_uses_no_verification_and_exposes_only_the_original_imports(self):
        search, *_ = self.prepare()
        calls = self.verification_calls
        request = baseline_search.next_request(search)
        self.assertEqual(request, baseline_search.next_request(search))
        inner = request["inner_request"]
        self.assertEqual(inner["condition"], "baseline")
        self.assertEqual([s["module"] for s in inner["sources"]], ["Base", "Tasks.D01"])
        self.retain(search)
        self.assertEqual(self.verification_calls, calls)
        self.assertIsNone(baseline_search.next_request(search))

    def test_wrong_and_stale_requests_cannot_consume_a_different_slot(self):
        search, *_ = self.prepare(methods=2)
        request = baseline_search.next_request(search)
        submission = {"action": "retain", "request_sha256": "0" * 64, "reason": "Fixture"}
        with self.assertRaises(CorpusError):
            baseline_search.submit(search, submission)
        self.assertEqual(request, baseline_search.next_request(search))
        submission["request_sha256"] = request["request_sha256"]
        baseline_search.submit(search, submission)
        current = baseline_search.next_request(search)
        with self.assertRaises(CorpusError):
            baseline_search.submit(search, submission)
        self.assertEqual(current, baseline_search.next_request(search))

    def test_clean_sweeps_restart_after_an_improvement(self):
        search, *_ = self.prepare(max_sweeps=3, stable_sweeps=2)
        first = self.candidate(search, cost=60)
        self.assertEqual(first["completed_sweeps"], 1)
        self.assertEqual(first["stable_sweeps"], 0)
        second = self.retain(search)
        self.assertEqual(second["stable_sweeps"], 1)
        self.assertIsNotNone(baseline_search.next_request(search))
        final = self.retain(search)
        self.assertEqual(final["completed_sweeps"], 3)
        self.assertEqual(final["stable_sweeps"], 2)
        self.assertEqual(final["status"], "declared_search_finished")
        for flag in ("baseline_search_complete", "package_attribution_ready", "globally_shortest",
                     "model_search_verified", "definition_optimization_performed"):
            self.assertIs(final[flag], False)
        self.assertIsNone(baseline_search.next_request(search))

    def test_every_task_and_method_is_required_for_a_clean_sweep(self):
        search, *_ = self.prepare(tasks=("d01", "d02"), methods=2)
        observed = []
        for slot in range(4):
            request = baseline_search.next_request(search)
            observed.append((request["task_id"], request["method"]["name"]))
            result = self.retain(search)
            self.assertEqual(result["completed_sweeps"], int(slot == 3))
        self.assertEqual(len(set(observed)), 4)
        self.assertIsNone(baseline_search.next_request(search))

    def test_partial_sweep_improvement_immediately_invalidates_prior_stability(self):
        search, *_ = self.prepare(tasks=("d01", "d02"), max_sweeps=3, stable_sweeps=2)
        self.retain(search)
        clean = self.retain(search)
        self.assertEqual(clean["stable_sweeps"], 1)
        changed = self.candidate(search, cost=50)
        self.assertEqual(changed["completed_sweeps"], 1)
        self.assertEqual(changed["stable_sweeps"], 0)
        self.assertEqual(baseline_search.next_request(search)["task_id"], "d02")

    def test_last_sweep_improvement_stops_at_cap_without_a_stable_sweep(self):
        search, *_ = self.prepare(max_sweeps=1)
        result = self.candidate(search, cost=60)
        self.assertEqual(result["stable_sweeps"], 0)
        self.assertEqual(result["completed_sweeps"], 1)
        self.assertIsNone(baseline_search.next_request(search))
        with self.assertRaises(CorpusError):
            baseline_search.submit(search, {"action": "retain", "request_sha256": "0" * 64,
                                            "reason": "Cannot exceed the frozen cap"})

    def test_rejected_inconclusive_and_interrupted_work_cannot_make_a_clean_sweep(self):
        for index, marker in enumerate(("_reject_fixture_", "_inconclusive_fixture_",
                                        "_interrupt_fixture_")):
            with self.subTest(marker=marker):
                search, *_ = self.prepare(max_sweeps=1, name="failure" + str(index))
                try:
                    self.candidate(search, cost=1, proof="by " + marker)
                except KeyboardInterrupt:
                    self.assertEqual(marker, "_interrupt_fixture_")
                result = baseline_search.report(search)
                self.assertEqual(result["selected_source_tokens"], 100)
                self.assertEqual(result["stable_sweeps"], 0)
                self.assertIsNone(baseline_search.next_request(search))
                self.assertTrue(result["attempts"])
                if marker == "_interrupt_fixture_":
                    artifact = next(search.rglob("attempts/d01/001"))
                    shutil.rmtree(artifact)
                    earlier_interruption = baseline_search.report(search)
                    self.assertEqual(earlier_interruption["status"], "interrupted_or_inconclusive")
                    self.assertEqual(earlier_interruption["selected_source_tokens"], 100)
                    self.assertIsNone(baseline_search.next_request(search))

    def test_submission_schema_cannot_smuggle_budgets_tools_or_unverified_usage(self):
        search, *_ = self.prepare()
        request = baseline_search.next_request(search)
        base = {"action": "candidate", "request_sha256": request["request_sha256"],
                "proof": "by _candidate_fixture_", "bridge": "Fixture only"}
        for field, value in (("task_id", "d02"), ("budget", 999), ("generation_usage", 0),
                             ("tools", ["Candidate"]), ("reason", "Ambiguous action")):
            with self.subTest(field=field), self.assertRaises(CorpusError):
                baseline_search.submit(search, {**base, field: value})
        self.assertEqual(request, baseline_search.next_request(search))

    def test_policy_limits_are_frozen_and_require_small_explicit_searches(self):
        search, inventory, policy, _ = self.prepare()
        invalid = []
        for field, value in (("max_sweeps", 0), ("max_sweeps", 5), ("max_sweeps", True),
                             ("stable_sweeps", 0), ("stable_sweeps", 3),
                             ("evidence_mode", "api"), ("schema_version", 2),
                             ("methods", []), ("methods", policy["methods"] * 2),
                             ("methods", [{"name": "bad/name", "instructions": "x"}])):
            invalid.append({**policy, field: value})
        invalid.append({**policy, "max_calls": 999})
        invalid.append({**policy, "methods": [{"name": "method" + str(i), "instructions": "x"}
                                                for i in range(4)]})
        for index, value in enumerate(invalid):
            with self.subTest(index=index), self.assertRaises(CorpusError):
                baseline_search.prepare_search(inventory, value, self.root / ("invalid" + str(index)))
        with self.assertRaises((CorpusError, FileExistsError)):
            baseline_search.prepare_search(inventory, policy, search)

    def test_frozen_copies_ignore_external_changes_and_reject_internal_tampering(self):
        search, inventory, _, seed = self.prepare()
        original = baseline_search.next_request(search)
        raw = inventory.read_bytes()
        changed = json.loads(raw)
        changed["tasks"][0]["selected"]["proof_source_tokens"] = 1
        inventory.write_text(json.dumps(changed))
        source = seed / "snapshot/Base.lean"
        source.write_bytes(source.read_bytes() + b"\n-- changed source fixture\n")
        self.assertEqual(baseline_search.next_request(search), original)
        for path in (search / "inventory.json", search / "snapshot/Base.lean",
                     search / "incumbents/d01/Proof.lean", search / "plan.json"):
            old = path.read_bytes()
            if path.name == "plan.json":
                changed = json.loads(old)
                changed["policy"]["max_sweeps"] = 4
                path.write_text(json.dumps(changed))
            else:
                path.write_bytes(old + b"\nchanged fixture\n")
            with self.subTest(path=path), self.assertRaises((CorpusError, ValueError)):
                baseline_search.report(search)
            path.write_bytes(old)

    def test_missing_response_or_result_stops_without_resetting_the_consumed_slot(self):
        for index, filename in enumerate(("response.json", "result.json")):
            with self.subTest(filename=filename):
                search, *_ = self.prepare(name="missing" + str(index))
                self.retain(search)
                (search / "attempts/0001" / filename).unlink()
                if filename == "response.json":
                    with self.assertRaises(CorpusError):
                        baseline_search.report(search)
                else:
                    result = baseline_search.report(search)
                    self.assertEqual(result["status"], "interrupted_or_inconclusive")
                    self.assertEqual(len(result["attempts"]), 1)
                    self.assertEqual(result["stable_sweeps"], 0)
                    self.assertIsNone(baseline_search.next_request(search))

    def test_deleting_a_whole_retain_record_cannot_reuse_the_consumed_slot(self):
        search, *_ = self.prepare(methods=2)
        self.retain(search)
        (search / "reservations/0001.json").unlink()
        shutil.rmtree(search / "attempts/0001")
        try:
            request = baseline_search.next_request(search)
        except CorpusError:
            return
        self.assertIsNone(request)
        self.assertEqual(baseline_search.report(search)["status"], "interrupted_or_inconclusive")

    def test_outer_reservation_without_an_issued_slot_is_rejected(self):
        search, *_ = self.prepare(methods=2)
        self.retain(search)
        request = baseline_search.next_request(search)
        response = {"action": "retain", "request_sha256": request["request_sha256"],
                    "reason": "Unissued fixture"}
        pending = {"slot": request["slot"], "request_sha256": request["request_sha256"],
                   "response_sha256": digest(canonical(response))}
        save_new(search / "reservations/0002.json", seal(pending))
        with self.assertRaises(CorpusError):
            baseline_search.report(search)

    def test_missing_issuance_journal_cannot_be_treated_as_an_unused_search(self):
        for index, submitted in enumerate((False, True)):
            with self.subTest(submitted=submitted):
                search, *_ = self.prepare(methods=2, name="journal" + str(index))
                if submitted:
                    self.retain(search)
                (search / "issued.jsonl").unlink()
                with self.assertRaises(CorpusError):
                    baseline_search.next_request(search)

    def test_interruption_after_issuance_before_reservation_still_consumes_the_slot(self):
        search, *_ = self.prepare(methods=2)
        request = baseline_search.next_request(search)
        response = {"action": "retain", "request_sha256": request["request_sha256"],
                    "reason": "Fixture interruption before reservation"}
        original_save = baseline_search.save_new

        def fail_reservation(path, value):
            if Path(path).parent.name == "reservations":
                raise OSError("Fixture failed write")
            return original_save(path, value)

        with patch.object(baseline_search, "save_new", side_effect=fail_reservation):
            with self.assertRaises(OSError):
                baseline_search.submit(search, response)
        result = baseline_search.report(search)
        self.assertEqual(result["status"], "interrupted_or_inconclusive")
        self.assertEqual(len(result["attempts"]), 1)
        self.assertEqual(result["selected_source_tokens"], 100)
        self.assertIsNone(baseline_search.next_request(search))

    def test_runtime_tool_changes_reject_existing_search_evidence(self):
        search, *_ = self.prepare()
        changed_tools = self.root / "changed-tools"
        for relative in baseline_search.TOOLS:
            target = changed_tools / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        source = changed_tools / "maam/baseline_search.py"
        source.write_bytes(source.read_bytes() + b"\n# changed runtime fixture\n")
        with patch.object(baseline_search, "REPO", changed_tools), self.assertRaises(CorpusError):
            baseline_search.report(search)

    def test_unreserved_inner_attempts_and_changed_replacement_proofs_are_rejected(self):
        for index, extra_attempt in enumerate((True, False)):
            with self.subTest(extra_attempt=extra_attempt):
                search, *_ = self.prepare(name="inner" + str(index))
                self.candidate(search, cost=50)
                proofs = list(search.rglob("attempts/d01/001/Proof.lean"))
                self.assertEqual(len(proofs), 1)
                proof = proofs[0]
                if extra_attempt:
                    inner = proof.parents[3]
                    request = task_request(inner, "d01")
                    try:
                        submit_attempt(inner, {"task_id": "d01",
                            "request_sha256": request["request_sha256"],
                            "proof": "by _undeclared_fixture_", "bridge": "Fixture only"})
                    except CorpusError:
                        self.assertEqual(baseline_search.report(search)["selected_source_tokens"], 50)
                        continue
                else:
                    proof.write_text(proof.read_text() + "\n-- changed replacement fixture\n")
                with self.assertRaises(CorpusError):
                    baseline_search.report(search)

    def test_original_coverage_and_conservative_claims_survive_partial_search(self):
        search, *_ = self.prepare(tasks=("d01", "d02"))
        result = self.candidate(search, cost=70)
        self.assertEqual(result["initial_source_tokens"], 200)
        self.assertEqual(result["selected_source_tokens"], 170)
        self.assertEqual(len(result["tasks"]), 2)
        self.assertIsNone(result["generation_usage"])
        for flag in ("baseline_search_complete", "package_attribution_ready", "globally_shortest",
                     "model_search_verified", "definition_optimization_performed"):
            self.assertIs(result[flag], False)
        self.assertEqual(result["actual_provider_calls"], 0)
        encoded = json.dumps(result)
        self.assertNotIn('"generation_usage": 0', encoded)

    def test_cli_preserves_existing_outputs_and_sanitizes_invalid_submissions(self):
        spec = importlib.util.spec_from_file_location(
            "control_baseline_search", ROOT / "scripts/control_baseline_search.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        search, *_ = self.prepare()
        output = self.root / "status.json"
        argv = ["status", "--root", str(search), "--output", str(output)]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(argv), 0)
            original = output.read_bytes()
            self.assertEqual(cli.main(argv), 2)
        self.assertEqual(output.read_bytes(), original)
        invalid = self.root / "invalid-submission.json"
        invalid.write_text(json.dumps({"action": "fixture_private_text"}))
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(cli.main(["submit", "--root", str(search), "--submission", str(invalid)]), 2)
        self.assertEqual(json.loads(stdout.getvalue()), {"status": "local_error", "kind": "CorpusError"})

    def test_cli_request_preserves_terminal_status_and_exit_semantics(self):
        spec = importlib.util.spec_from_file_location(
            "control_baseline_search", ROOT / "scripts/control_baseline_search.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        cases = (("sweep_budget_exhausted", 2), ("interrupted_or_inconclusive", 2),
                 ("declared_search_finished", 0))
        for index, (status, code) in enumerate(cases):
            with self.subTest(status=status):
                search, *_ = self.prepare(max_sweeps=1, name="terminal" + str(index))
                if status == "sweep_budget_exhausted":
                    self.candidate(search, cost=50)
                elif status == "interrupted_or_inconclusive":
                    self.candidate(search, proof="by _inconclusive_fixture_")
                else:
                    self.retain(search)
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    self.assertEqual(cli.main(["request", "--root", str(search)]), code)
                self.assertEqual(json.loads(stdout.getvalue())["status"], status)


if __name__ == "__main__":
    unittest.main()
