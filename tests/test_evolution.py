import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from maam import evolution as ev
from maam.corpus import CorpusError
from maam.migration import save_new, seal, task_request, unseal
from maam.theory import digest

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "experiments/hom_kernel_evolution/study.json"
SKILL = ROOT / "skills/evaluate-theory-package"


class EvolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.exp = self.folder / "input"
        shutil.copytree(STUDY.parent, self.exp, ignore=shutil.ignore_patterns("*.olean"))
        self.path = self.exp / "study.json"
        self.data = json.loads(self.path.read_text())
        self.run, self.workers = self.folder / "run", self.folder / "workers"

    def write(self):
        self.path.write_text(json.dumps(self.data, indent=2) + "\n")

    def prepare(self):
        self.write()
        return ev.prepare(self.path, self.run, self.workers, SKILL, "a" * 40)

    def submitted_failure(self, number=1):
        row = self.data["launch_order"][0]
        worker = self.workers / row["worker"]
        request = json.loads((worker / "request.json").read_text())
        proof, bridge = "by\n  exact False.elim (by trivial)\n", "Deliberately invalid fixture."
        (worker / f"proof-{number:02d}.lean").write_text(proof)
        (worker / f"bridge-{number:02d}.txt").write_text(bridge)
        save_new(worker / f"submission-{number:02d}.json", {"task_id": row["task_id"],
            "request_sha256": request["request_sha256"], "proof": proof, "bridge": bridge})
        with patch("maam.evolution.shutil.which", return_value="/test/lean"), patch(
                "maam.migration.verify_attempt", return_value={"status": "rejected", "trace": [],
                "audit": None, "failure": {"kind": "verification_failed", "stage": "compile:Proof", "message": "test fixture"}}):
            return ev.verify_return(self.run, row["worker"], number)

    def test_parent_is_byte_identical_to_previous_frozen_package(self):
        study = ev.load_study(self.path)
        self.assertEqual(len(study["manifest"]["launch_order"]), 12)
        for name in ("Base.lean", "Candidate.lean"):
            self.assertEqual((self.exp / name).read_bytes(),
                (ROOT / "experiments/hom_kernel_independent" / name).read_bytes())

    def test_parent_cycles_rejected(self):
        self.data["versions"][0]["parent"] = "v2"
        self.write()
        with self.assertRaisesRegex(CorpusError, "parent must"):
            ev.load_study(self.path)

    def test_ancestor_module_replacement_rejected_even_with_new_hash(self):
        changed = self.exp / "Changed.lean"
        changed.write_text((self.exp / "Candidate.lean").read_text() + "\n-- changed\n")
        self.data["versions"][1]["sources"]["Candidate"] = {"path": "Changed.lean", "sha256": digest(changed.read_bytes())}
        self.write()
        with self.assertRaisesRegex(CorpusError, "preserve parent"):
            ev.load_study(self.path)

    def test_later_use_cannot_precede_introduction(self):
        self.data["versions"][1]["introduced_round"] = 2
        self.write()
        with self.assertRaisesRegex(CorpusError, "follow package introduction"):
            ev.load_study(self.path)

    def test_different_task_context_cannot_be_compared(self):
        path = self.exp / "suite-v2.json"
        suite = json.loads(path.read_text())
        suite["tasks"][0]["goal"] = "Tasks.differentGoal"
        path.write_text(json.dumps(suite))
        self.data["variants"][2]["suite"]["sha256"] = digest(path.read_bytes())
        self.write()
        with self.assertRaisesRegex(CorpusError, "share foundation, tasks"):
            ev.load_study(self.path)

    def test_unmeasured_generation_cannot_be_declared_fair(self):
        self.data["scope"]["generation_budget_verified"] = True
        self.write()
        with self.assertRaisesRegex(CorpusError, "cannot certify"):
            ev.load_study(self.path)

    def test_duplicate_worker_rejected(self):
        self.data["launch_order"][1]["worker"] = self.data["launch_order"][0]["worker"]
        self.write()
        with self.assertRaisesRegex(CorpusError, "unique workers"):
            ev.load_study(self.path)

    def test_requests_have_one_goal_and_only_their_version(self):
        self.prepare()
        for row in self.data["launch_order"]:
            request = json.loads((self.workers / row["worker"] / "request.json").read_text())
            modules = [s["module"] for s in request["sources"]]
            self.assertEqual(sum(m.startswith("Tasks.") for m in modules), 1)
            self.assertEqual("Candidate" in modules, row["variant"] != "baseline")
            self.assertEqual("Extension" in modules, row["variant"] == "v2")

    def test_controller_and_workers_cannot_share_directory(self):
        with self.assertRaisesRegex(CorpusError, "separate"):
            ev.prepare(self.path, self.run, self.run / "workers", SKILL, "a" * 40)

    def test_launch_order_and_context_reuse_rejected(self):
        self.prepare()
        first, second = self.data["launch_order"][:2]
        with self.assertRaisesRegex(CorpusError, "fresh contexts"):
            ev.register(self.run, second["worker"], "agent-b")
        ev.register(self.run, first["worker"], "agent-a")
        with self.assertRaisesRegex(CorpusError, "fresh contexts"):
            ev.register(self.run, second["worker"], "agent-a")

    def test_unknown_generation_is_null_and_empty_run_is_incomplete(self):
        self.prepare()
        result = ev.summarize(self.run)
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["generation"]["input_tokens"])
        self.assertTrue(all(p["cost_relation"] == "undetermined" for p in result["pairs"]))
        with self.assertRaisesRegex(CorpusError, "incomplete cohort"):
            ev.export_run(self.run, self.folder / "export")

    def test_missing_child_lean_does_not_consume_budget(self):
        self.prepare()
        row = self.data["launch_order"][0]
        ev.register(self.run, row["worker"], "agent-a")
        with patch("maam.evolution.shutil.which", return_value=None):
            with self.assertRaisesRegex(CorpusError, "expose child lean"):
                ev.verify_return(self.run, row["worker"], 1)
        self.assertEqual(list((self.run / "returns").iterdir()), [])
        self.assertEqual(list((self.run / row["variant"] / "reservations").iterdir()), [])

    def test_failed_attempts_remain_in_budget_and_feedback(self):
        self.prepare()
        row = self.data["launch_order"][0]
        ev.register(self.run, row["worker"], "agent-a")
        for number in range(1, 4):
            self.assertEqual(self.submitted_failure(number)["remaining_attempts"], 3-number)
        self.assertEqual(ev.summarize(self.run)["attempts"], 3)
        with patch("maam.evolution.shutil.which", return_value="/test/lean"):
            with self.assertRaisesRegex(CorpusError, "consecutive attempts"):
                ev.verify_return(self.run, row["worker"], 4)
        self.assertEqual(len(list((self.run / "returns").iterdir())), 3)

    def test_resealed_feedback_change_rejected(self):
        self.prepare()
        row = self.data["launch_order"][0]
        ev.register(self.run, row["worker"], "agent-a")
        self.submitted_failure()
        path = self.run / "feedback" / (row["worker"] + "-001.json")
        value = unseal(path); value["remaining_attempts"] = 3
        path.write_text(json.dumps(seal(value)))
        with self.assertRaisesRegex(CorpusError, "feedback changed"):
            ev.summarize(self.run)

    def test_evaluator_change_rejected(self):
        self.prepare()
        path = self.run / "run.json"
        value = unseal(path); value["evaluators"]["evolution.py"] = "0" * 64
        path.write_text(json.dumps(seal(value)))
        with self.assertRaisesRegex(CorpusError, "evaluator changed"):
            ev.run_record(self.run)

    def test_dependency_paths_follow_helpers_and_terminate_on_cycles(self):
        proof = {"declarations": [{"name": "Submission.solve", "direct_dependencies": ["local.helper"]},
                 {"name": "local.helper", "direct_dependencies": ["Theory.new", "Submission.solve"]}]}
        packages = [{"declarations": [{"name": "Theory.new", "direct_dependencies": ["Theory.old"]},
                     {"name": "Theory.old", "direct_dependencies": []},
                     {"name": "Theory.unused", "direct_dependencies": []}]}]
        paths = ev.dependency_paths(proof, packages)
        self.assertEqual(paths["Theory.old"], ["Submission.solve", "local.helper", "Theory.new", "Theory.old"])
        self.assertNotIn("Theory.unused", paths)


if __name__ == "__main__":
    unittest.main()
