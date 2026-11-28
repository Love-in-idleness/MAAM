"""Grouped protocol regressions with explicitly mocked Lean verification."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from maam import CorpusError, grouped_search as gs
from maam.migration import seal, unseal
from maam.theory import digest

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "experiments/grouped_search_v1/plan.json"


class GroupedSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "group"
        self.verifier = patch("maam.migration.verify_attempt", side_effect=self.verify).start()
        self.addCleanup(patch.stopall)
        gs.start(PLAN, self.root, solver_id="mocked-verifier", mode="supplied_reference")

    def verify(self, frozen, request, source, artifact, **kwargs):
        if "_interrupt_" in source:
            raise KeyboardInterrupt("fixture interruption")
        if "_reject_" in source:
            return {"status": "rejected", "trace": [], "audit": None,
                    "failure": {"kind": "fixture_rejection"}}
        return {"status": "verified", "trace": [], "audit": {
            "targets": [{"name": "Submission.solve", "expected": "GroupGoal.goal",
                         "goal_preserved": True, "proof_expr_nodes": 50}],
            "sources": [{"module": "Proof", "source_tokens": len(source)}]}}

    def retain(self, phase):
        request = gs.request(self.root, phase)
        return gs.submit(self.root, phase, {"action": "retain",
            "request_sha256": request["request_sha256"], "reason": "Fixture retains incumbent"})

    def freeze(self):
        self.retain("preparation")
        self.retain("preparation")
        return gs.freeze(self.root)

    def candidate(self, phase, *, helper="", marker="", request=None):
        request = request or gs.request(self.root, phase)
        return {"action": "candidate", "request_sha256": request["request_sha256"],
                "helpers": helper, "proofs": {"one": "by " + marker + " trivial",
                                              "two": "by trivial"},
                "bridge": "Mocked-verification fixture only"}

    def test_freeze_barrier_and_bounded_idempotent_requests(self):
        for phase in ("control", "treatment"):
            with self.assertRaises(CorpusError):
                gs.request(self.root, phase)
        with self.assertRaises(CorpusError):
            gs.freeze(self.root)
        first = gs.request(self.root, "preparation")
        self.assertEqual(first, gs.request(self.root, "preparation"))
        self.retain("preparation")
        second = gs.request(self.root, "preparation")
        self.assertNotEqual(first["request_sha256"], second["request_sha256"])
        self.retain("preparation")
        with self.assertRaises(CorpusError):
            gs.request(self.root, "preparation")
        self.assertTrue(gs.freeze(self.root)["preparation_frozen"])
        with self.assertRaises(CorpusError):
            gs.request(self.root, "preparation")

    def test_condition_specific_sources_common_prepared_pool_and_own_feedback(self):
        self.freeze()
        control = gs.request(self.root, "control")
        treatment = gs.request(self.root, "treatment")
        self.assertEqual([s["module"] for s in control["inner_request"]["sources"]], ["Base", "GroupGoal"])
        self.assertEqual([s["module"] for s in treatment["inner_request"]["sources"]],
                         ["Base", "GroupGoal", "Candidate"])
        self.assertNotIn("Calibration.keep", json.dumps(control))
        self.assertEqual(control["prepared_sha256"], treatment["prepared_sha256"])
        gs.submit(self.root, "control", self.candidate("control", marker="_reject_", request=control))
        second = gs.request(self.root, "control")
        self.assertEqual(len(second["prior_feedback"]), 1)
        self.assertEqual(gs.request(self.root, "treatment")["prior_feedback"], [])
        self.assertEqual(second["prepared_sha256"], treatment["prepared_sha256"])

    def test_component_coverage_wrong_phase_and_stale_response_do_not_consume_slot(self):
        self.freeze()
        control = gs.request(self.root, "control")
        response = self.candidate("control", request=control)
        incomplete = copy.deepcopy(response)
        incomplete["proofs"].pop("two")
        with self.assertRaises(CorpusError):
            gs.submit(self.root, "control", incomplete)
        gs.request(self.root, "treatment")
        with self.assertRaises(CorpusError):
            gs.submit(self.root, "treatment", response)
        self.assertEqual(gs.request(self.root, "control"), control)
        self.retain("control")
        gs.request(self.root, "control")
        with self.assertRaises(CorpusError):
            gs.submit(self.root, "control", response)

    def test_shared_helper_source_charged_once_and_control_can_invent_it(self):
        self.freeze()
        response = self.candidate("control", helper="have keep : True := True.intro")
        result = gs.submit(self.root, "control", response)
        source = (self.root / result["artifact"] / "Proof.lean").read_text()
        self.assertEqual(source.count("have keep"), 1)
        self.assertIn("show Calibration.GoalOne", source)
        self.assertIn("show Calibration.GoalTwo", source)
        report = gs.report(self.root)
        self.assertEqual(report["verified_complete_routes"], 2)
        route = report["measurement"]["routes"][-1]
        self.assertEqual(route["costs"]["complete"]["source_utf8_bytes"], len(source.encode()))
        self.assertFalse(report["generation_budget_verified"])

    def test_interrupted_and_rejected_candidates_consume_the_declared_slots(self):
        self.freeze()
        with self.assertRaises(KeyboardInterrupt):
            gs.submit(self.root, "control", self.candidate("control", marker="_interrupt_"))
        report = gs.report(self.root)
        self.assertEqual(report["stages"]["control"]["outcomes"][0]["status"], "interrupted")
        gs.submit(self.root, "control", self.candidate("control", marker="_reject_"))
        with self.assertRaises(CorpusError):
            gs.request(self.root, "control")
        self.assertEqual(gs.report(self.root)["verified_complete_routes"], 1)

    def test_missing_decision_or_snapshot_mutation_is_rejected(self):
        self.retain("preparation")
        decision = self.root / "decisions/preparation-001.result.json"
        content = decision.read_bytes()
        decision.unlink()
        with self.assertRaises((CorpusError, OSError)):
            gs.report(self.root)
        decision.write_bytes(content)
        base = self.root / "snapshot/Base.lean"
        base.write_bytes(base.read_bytes() + b"\n-- mutation")
        with self.assertRaises(CorpusError):
            gs.report(self.root)

    def test_complete_schedule_keeps_unknown_generation_and_fixed_budget(self):
        self.freeze()
        for phase in ("control", "treatment"):
            self.retain(phase)
            self.retain(phase)
        report = gs.report(self.root)
        self.assertEqual(report["status"], "grouped_schedule_complete")
        self.assertEqual(report["attempt_cap_per_stage"], 2)
        self.assertIsNone(report["generation_usage"])
        self.assertFalse(report["training_eligible"])
        self.assertFalse(report["measurement"]["causal_effect_established"])

    def test_lock_and_byte_cap_preserve_request(self):
        self.freeze()
        request = gs.request(self.root, "control")
        response = self.candidate("control", helper=" " * 40000, request=request)
        with self.assertRaises(CorpusError):
            gs.submit(self.root, "control", response)
        (self.root / "controller.lock").write_text("fixture")
        with self.assertRaises(CorpusError):
            gs.request(self.root, "control")
        (self.root / "controller.lock").unlink()
        self.assertEqual(request, gs.request(self.root, "control"))

    def test_resealed_control_cannot_gain_treatment_sources(self):
        path = self.root / "control/session.json"
        record = unseal(path)
        record["condition"] = "treatment"
        path.write_text(json.dumps(seal(record)))
        with self.assertRaises(CorpusError):
            gs.report(self.root)

    def test_missing_candidate_preflight_cannot_admit_search(self):
        path = self.root / "candidate_check/attempts/group/001/result.json"
        path.unlink()
        with self.assertRaises(CorpusError):
            gs.request(self.root, "preparation")

    def test_dotted_module_names_and_measured_labels_cannot_collide(self):
        folder = Path(self.temp.name) / "alternate"
        folder.mkdir()
        plan = json.loads(PLAN.read_text())
        for module in ("Base", "Candidate"):
            (folder / (module + ".lean")).write_bytes((PLAN.parent / (module + ".lean")).read_bytes())
        for number, module in enumerate(("Aux.One", "Aux_One", "GroupMeasured.Route0000")):
            path = folder / f"extra-{number}.lean"
            content = f"-- independent module {module}\nimport Init\n".encode()
            path.write_bytes(content)
            plan["base"]["modules"].append(module)
            plan["sources"][module] = {"path": path.name, "sha256": digest(content)}
        path = folder / "plan.json"
        path.write_text(json.dumps(plan))
        result = gs.start(path, folder / "run", solver_id="mocked-verifier")
        self.assertEqual(result["verified_complete_routes"], 1)
        self.assertNotIn("GroupMeasured.Route0000", result["measurement"]["routes"][0]["costs"]["complete"]["charged_modules"])


class GroupedMethodsTests(unittest.TestCase):
    def test_methods_use_only_the_exported_target_ids_and_share_one_helper(self):
        from maam.grouped_methods import generate
        request = {"slot": 1, "targets": [{"id": "a", "goal": "Test.A"},
                    {"id": "b", "goal": "Test.B"}], "request_sha256": "fixture"}
        direct = generate(request)
        self.assertEqual(set(direct["proofs"]), {"a", "b"})
        self.assertEqual(direct["helpers"], "")
        shared = generate({**request, "slot": 2})
        self.assertEqual(shared["helpers"].count("have reuse"), 1)
        self.assertIn("unfold Test.A", shared["proofs"]["a"])
        self.assertIn("unfold Test.B", shared["proofs"]["b"])
        self.assertEqual(generate({**request, "slot": 3})["action"], "retain")

    def test_invalid_method_slots_reject(self):
        from maam.grouped_methods import generate
        for slot in (False, 0, -1, "2"):
            with self.assertRaises(CorpusError):
                generate({"slot": slot})
