"""Offline portfolio composition; Lean audits below are explicit test fixtures."""
from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from maam import CorpusError, migration
from maam.baseline import inventory_baseline
from maam.theory import digest
from scripts import measure_compressed_reference as compression
from scripts import measure_retained_portfolio as measurement


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "experiments/metered_transfer_v1/suite.json"


class RetainedCompressionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.baseline = self.work / "baseline"
        self.treatment = self.work / "treatment"
        self.stability_root = self.work / "stability"
        self.stability_root.mkdir()
        self.tokens = {"d01": 100, "d02": 100}
        self.verification = self.enterContext(patch(
            "maam.migration.verify_attempt", side_effect=self.verify_fixture))
        self.network = self.enterContext(patch(
            "urllib.request.urlopen", side_effect=AssertionError("offline fixture only")))
        migration.start_session(SUITE, self.baseline, condition="baseline", solver_id="unit-fixture")
        self.submit(self.baseline, "d01", "by exact fixture_original_one")
        self.submit(self.baseline, "d02", "by exact fixture_original_two")
        self.inventory = inventory_baseline([self.baseline], ["d01", "d02"])
        self.state = {
            "schema_version": 1, "status": "declared_method_preparation_complete",
            "declared_method_preparation_complete": True, "task_ids": ["d01", "d02"],
            "baseline_search_complete": False, "package_attribution_ready": False,
            "globally_shortest": False, "selected_source_tokens": 200,
        }
        self.replay = self.enterContext(patch.object(
            measurement.stability, "_replay", side_effect=lambda root: (self.state, self.inventory)))
        migration.start_session(SUITE, self.treatment, condition="treatment", solver_id="unit-fixture")
        self.tokens = {"d01": 50, "d02": 150}
        self.submit(self.treatment, "d01", "by exact fixture_alternative_one")
        self.submit(self.treatment, "d02", "by exact fixture_alternative_two")

    def verify_fixture(self, frozen, request, source, artifact, **kwargs):
        treatment = request["condition"] == "treatment"
        package = frozen["package"]["modules"] if treatment else []
        sources = [
            {"module": module, "source_tokens": 30 + index,
             "source_utf8_bytes": len(frozen["blobs"][module])}
            for index, module in enumerate(package)
        ]
        sources.append({"module": "Proof", "source_tokens": self.tokens[request["task"]["id"]],
                        "source_utf8_bytes": len(source.encode("utf-8"))})
        return {"status": "verified", "trace": [], "audit": {
            "lean_version": frozen["manifest"]["lean_version"], "module": "Proof",
            "imported_modules": [s["module"] for s in request["sources"]],
            "package_declarations": frozen["package"]["declarations"] if treatment else [],
            "axioms_used": [], "targets": [{"name": "Submission.solve",
                "expected": request["task"]["goal"], "goal_preserved": True,
                "proof_expr_nodes": 20, "source": {
                    "signature_tokens": 6, "body_tokens": 4, "declaration_tokens": 11}}],
            "sources": sources}}

    def submit(self, root, task, proof):
        request = migration.task_request(root, task)
        return migration.submit_attempt(root, {
            "task_id": task, "request_sha256": request["request_sha256"],
            "proof": proof, "bridge": "Unit fixture; no real Lean verification"})

    def build(self):
        return measurement.build_report(self.stability_root, self.treatment)

    def artifact(self, root, task="d01"):
        return root / "attempts" / task / "001"

    def change_result(self, root, mutate, task="d01"):
        path = self.artifact(root, task) / "result.json"
        result = migration.unseal(path)
        mutate(result)
        path.write_bytes(migration.canonical(migration.seal(result)))

    def test_shorter_only_replacement_preserves_exact_original_imports(self):
        before = self.verification.call_count
        result = self.build()
        rows = result["retained_portfolio"]["tasks"]
        self.assertEqual([r["action"] for r in rows], ["replace_with_shorter", "retain_original"])
        original = self.inventory["tasks"][1]["selected"]
        for field in ("proof_source_tokens", "proof_sha256", "result_sha256", "artifact", "request_sha256"):
            self.assertEqual(rows[1]["selected"][field], original[field])
        self.assertEqual(rows[1]["selected"]["import_context"], original["original_import_context"])
        self.assertNotIn("Candidate", [m["module"] for m in rows[1]["selected"]["import_context"]])
        self.assertEqual(result["retained_portfolio"]["original_goal_source_ledger"], {
            "baseline_tokens": 200, "selected_proof_tokens": 150, "gross_tokens_saved": 50,
            "package_tokens_charged_once": 61, "selected_including_package_tokens": 211,
            "net_tokens_saved": -11})
        self.assertEqual(self.verification.call_count, before)
        self.network.assert_not_called()

    def test_payload_charges_package_once_and_keeps_both_proof_modules(self):
        result = self.build()
        _, _, frozen = migration.load_session(self.treatment)
        original = {task + "/Proof": (self.artifact(self.baseline, task) / "Proof.lean").read_bytes()
                    for task in ("d01", "d02")}
        retained = {"d01/Proof": (self.artifact(self.treatment) / "Proof.lean").read_bytes(),
                    "d02/Proof": original["d02/Proof"],
                    **{m: frozen["blobs"][m] for m in frozen["package"]["modules"]}}
        common = {m: frozen["blobs"][m] for m in ("Base", "Tasks.D01", "Tasks.D02")}
        for scope, shared in (("nonshared_payload", {}), ("standalone_sources", common)):
            row = result["scopes"][scope]
            self.assertEqual(row["conditions"]["baseline"], compression.measure_sources({**shared, **original}))
            self.assertEqual(row["conditions"]["retained_treatment"],
                             compression.measure_sources({**shared, **retained}))
            self.assertEqual(row["net_zlib_bytes_saved"],
                             row["conditions"]["baseline"]["compressed"]["zlib-9"]["bytes"]
                             - row["conditions"]["retained_treatment"]["compressed"]["zlib-9"]["bytes"])

    def test_equal_longer_and_missing_alternatives_keep_original(self):
        for cost in (100, 150, None):
            with self.subTest(cost=cost):
                def mutate(result):
                    if cost is None:
                        result.update(status="rejected", audit=None)
                    else:
                        result["audit"]["sources"][-1]["source_tokens"] = cost
                self.change_result(self.treatment, mutate)
                report = self.build()
                self.assertEqual([row["action"] for row in report["retained_portfolio"]["tasks"]],
                                 ["retain_original", "retain_original"])
                self.assertEqual(report["retained_portfolio"]["original_goal_source_ledger"][
                    "package_tokens_charged_once"], 61)
    def test_no_verified_alternative_cannot_invent_zero_package_cost(self):
        for task in ("d01", "d02"):
            self.change_result(self.treatment, lambda r: r.update(status="rejected", audit=None), task)
        with self.assertRaises(CorpusError):
            self.build()

    def test_unfinished_baseline_or_different_knowledge_is_rejected(self):
        self.state["declared_method_preparation_complete"] = False
        with self.assertRaises(CorpusError):
            self.build()
        self.state["declared_method_preparation_complete"] = True
        original = copy.deepcopy(self.inventory["knowledge"])
        changes = (("lean_version", "4.25.0"),
                   ("base", {**original["base"], "id": "different-base"}),
                   ("tasks", [{**original["tasks"][0], "goal": "Different.goal"}, original["tasks"][1]]),
                   ("source_sha256", {**original["source_sha256"], "Base": "0" * 64}))
        for field, value in changes:
            with self.subTest(field=field):
                self.inventory["knowledge"] = {**original, field: value}
                with self.assertRaises(CorpusError):
                    self.build()
        self.inventory["knowledge"] = original

    def test_changed_proof_bytes_or_submission_is_rejected(self):
        proof = self.artifact(self.treatment) / "Proof.lean"
        original = proof.read_bytes()
        proof.write_bytes(original + b"\n-- tampered\n")
        with self.assertRaises(CorpusError):
            self.build()
        proof.write_bytes(original)
        submission = self.artifact(self.treatment) / "submission.json"
        value = json.loads(submission.read_text())
        value["proof"] += "\n-- changed submission"
        submission.write_text(json.dumps(value))
        with self.assertRaises(CorpusError):
            self.build()

    def test_resealed_extra_import_cannot_bypass_exact_proof_reconstruction(self):
        artifact = self.artifact(self.treatment)
        source = artifact / "Proof.lean"
        source.write_bytes(b"import Std\n" + source.read_bytes())
        fingerprint = digest(source.read_bytes())
        for path in (self.treatment / "reservations/d01-001.json", artifact / "pending.json"):
            value = migration.unseal(path)
            value["proof_sha256"] = fingerprint
            path.write_bytes(migration.canonical(migration.seal(value)))

        def mutate(result):
            result["proof_sha256"] = fingerprint
            result["audit"]["sources"][-1]["source_utf8_bytes"] = len(source.read_bytes())
        self.change_result(self.treatment, mutate)
        # The generic session replay binds bytes, but does not rebuild the source.
        self.assertEqual(migration.session_report(self.treatment)["tasks"][0]["status"], "verified")
        with self.assertRaises(CorpusError):
            self.build()

    def test_resealed_audit_must_charge_complete_sources_and_exact_bytes(self):
        path = self.artifact(self.treatment) / "result.json"
        original = migration.unseal(path)
        cases = (
            lambda a: a["sources"].pop(0),
            lambda a: a["sources"].append(dict(a["sources"][0])),
            lambda a: a["sources"][0].update(source_utf8_bytes=1),
            lambda a: a["sources"][-1].update(source_utf8_bytes=1),
            lambda a: a["sources"][0].update(source_tokens=True),
            lambda a: a.update(axioms_used=["unapproved.axiom"]),
            lambda a: a["targets"][0].update(expected="Different.goal"),
        )
        for index, mutate in enumerate(cases):
            value = copy.deepcopy(original)
            mutate(value["audit"])
            path.write_bytes(migration.canonical(migration.seal(value)))
            with self.subTest(case=index), self.assertRaises(CorpusError):
                self.build()
        path.write_bytes(migration.canonical(migration.seal(original)))

    def test_package_token_cost_must_match_across_verified_tasks(self):
        self.change_result(self.treatment, lambda r: r["audit"]["sources"][0].update(
            source_tokens=99), task="d02")
        with self.assertRaises(CorpusError):
            self.build()

    def test_strict_replay_rejects_changed_measurement_and_integer_type(self):
        path = self.work / "measurement.json"
        report = self.build()
        path.write_bytes(migration.canonical(report))
        measurement.check_report(path, self.stability_root, self.treatment)
        for value in (True, 1.0):
            changed = {**report, "schema_version": value}
            path.write_bytes(migration.canonical(changed))
            with self.subTest(value=value), self.assertRaises(CorpusError):
                measurement.check_report(path, self.stability_root, self.treatment)
        report["scopes"]["nonshared_payload"]["net_zlib_bytes_saved"] += 1
        path.write_bytes(migration.canonical(report))
        with self.assertRaises(CorpusError):
            measurement.check_report(path, self.stability_root, self.treatment)

    def test_cli_creates_replays_and_never_overwrites(self):
        path = self.work / "measurement.json"
        common = ["--baseline-root", str(self.stability_root), "--treatment-session", str(self.treatment)]
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(measurement.main(common + ["--output", str(path)]), 0)
            original = path.read_bytes()
            self.assertEqual(measurement.main(common + ["--check", str(path)]), 0)
            self.assertEqual(measurement.main(common + ["--output", str(path)]), 2)
        self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
