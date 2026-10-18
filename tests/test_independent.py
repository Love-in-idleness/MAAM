import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from maam.corpus import CorpusError
from maam.independent import (bundle, infrastructure_failure, load_protocol,
                              prepare_run, register_launch, restore_archive,
                              restore_bundle, summarize, verify_return)
from maam.migration import seal, session_report, task_request, unseal

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "experiments/hom_kernel_independent/protocol.json"
SKILL = ROOT / "skills/evaluate-theory-package"


class IndependentProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def prepare(self):
        run, workers = self.folder / "controller", self.folder / "workers"
        prepare_run(PROTOCOL, run, workers, SKILL, freeze_commit="1" * 40)
        return run, workers

    def test_frozen_candidate_predates_twenty_new_goals(self):
        protocol, suite = load_protocol(PROTOCOL)
        self.assertEqual(len(protocol["launch_order"]), 40)
        self.assertEqual(len(json.loads(suite.read_text())["tasks"]), 20)
        self.assertEqual((suite.parent / "Candidate.lean").read_bytes(),
                         (ROOT / "experiments/hom_kernel/Candidate.lean").read_bytes())
        self.assertFalse(protocol["scope"]["generation_budget_verified"])
        self.assertIsNone(protocol["solver"]["model_revision"])

    def test_task_local_requests_exclude_opposite_condition(self):
        run, workers = self.prepare()
        for worker in ("w01", "w02"):
            request = json.loads((workers / worker / "request.json").read_text())
            modules = [s["module"] for s in request["sources"]]
            self.assertEqual([m for m in modules if m.startswith("Tasks.")], [request["task"]["module"]])
            self.assertEqual("Candidate" in modules, request["condition"] == "treatment")
        self.assertEqual(task_request(run / "baseline", "d06")["task"],
                         task_request(run / "treatment", "d06")["task"])

    def test_order_and_fresh_identity_are_required(self):
        run, _ = self.prepare()
        with self.assertRaisesRegex(CorpusError, "frozen launch order"):
            register_launch(run, "w02", "agent-2")
        register_launch(run, "w01", "agent-1")
        with self.assertRaisesRegex(CorpusError, "fresh context"):
            register_launch(run, "w02", "agent-1")
        register_launch(run, "w02", "agent-2")

    def test_changed_prompt_is_rejected(self):
        run, _ = self.prepare()
        p = run / "prompts/w01.txt"
        p.write_text(p.read_text() + "\nAn answer from the other condition.")
        with self.assertRaisesRegex(CorpusError, "prompt differs"):
            register_launch(run, "w01", "agent-1")

    def test_missing_child_toolchain_does_not_consume_attempt(self):
        run, _ = self.prepare()
        register_launch(run, "w01", "agent-1")
        with patch("maam.independent.shutil.which", return_value=None):
            with self.assertRaisesRegex(CorpusError, "PATH"):
                verify_return(run, "w01", 1)
        self.assertEqual(list((run / "baseline/reservations").iterdir()), [])
        self.assertEqual(list((run / "returns").iterdir()), [])
        self.assertTrue(all(not t["attempts"] for t in session_report(run / "baseline")["tasks"]))

    def test_worker_directory_cannot_contain_controller(self):
        with self.assertRaisesRegex(CorpusError, "separate"):
            prepare_run(PROTOCOL, self.folder / "run", self.folder / "run/workers", SKILL,
                        freeze_commit="1" * 40)

    def test_skill_edits_fail_before_creating_run(self):
        import shutil
        skill = self.folder / "skill"
        shutil.copytree(SKILL, skill)
        (skill / "SKILL.md").write_text("changed")
        with self.assertRaisesRegex(CorpusError, "frozen skill"):
            prepare_run(PROTOCOL, self.folder / "run", self.folder / "workers", skill,
                        freeze_commit="1" * 40)
        self.assertFalse((self.folder / "run").exists())

    def test_bundle_rejects_mutation_and_path_escape(self):
        source = self.folder / "source"
        source.mkdir()
        (source / "proof.lean").write_text("by exact True.intro\n")
        value = bundle(source)
        changed = copy.deepcopy(value)
        changed["files"]["proof.lean"] = "by sorry"
        with self.assertRaisesRegex(CorpusError, "fingerprint"):
            restore_bundle(changed, self.folder / "bad")
        escaped = seal({"files": {"../escape": "x"}})
        with self.assertRaises(CorpusError):
            restore_bundle(escaped, self.folder / "restore")
        restore_bundle(value, self.folder / "good")
        self.assertEqual(bundle(self.folder / "good"), value)

    def test_infrastructure_failure_is_not_general_proof_rejection(self):
        failure = {"status": "rejected", "failure": {"stage": "audit",
                    "message": "could not execute external process 'lean'"}}
        self.assertTrue(infrastructure_failure(failure))
        failure["failure"]["stage"] = "compile:Proof"
        self.assertFalse(infrastructure_failure(failure))
        failure["failure"] = {"stage": "audit", "message": "forbidden axiom: sorryAx"}
        self.assertFalse(infrastructure_failure(failure))

    def archived_run(self):
        run = self.folder / "restored"
        restore_archive(ROOT / "results/independent", run)
        return run

    def rewrite_record(self, path, value):
        path.write_text(json.dumps(seal(value), ensure_ascii=False, indent=2) + "\n")

    def test_resealed_opposite_worker_feedback_is_rejected(self):
        run = self.archived_run()
        path = run / "feedback/w01-002.json"
        feedback = unseal(path)
        feedback["worker"] = "w02"
        self.rewrite_record(path, feedback)
        with self.assertRaisesRegex(CorpusError, "own-condition feedback"):
            summarize(run)

    def test_erasing_environment_failure_cannot_restore_budget(self):
        import shutil
        run = self.archived_run()
        (run / "baseline/reservations/d06-001.json").unlink()
        shutil.rmtree(run / "baseline/attempts/d06/001")
        with self.assertRaises(CorpusError):
            summarize(run)

    def test_resealed_return_cannot_replace_original_proof(self):
        run = self.archived_run()
        path = run / "returns/w01-002.json"
        returned = unseal(path)
        returned["submission"]["proof"] = "by sorry"
        self.rewrite_record(path, returned)
        with self.assertRaisesRegex(CorpusError, "returned artifact"):
            summarize(run)

    def test_resealed_inventory_cannot_shrink_target(self):
        run = self.archived_run()
        path = run / "baseline/attempts/d06/002/measurement/result.json"
        measured = unseal(path)
        module = measured["inventory"]["modules"][-1]
        target = next(d for d in module["declarations"] if d["name"] == "Submission.solve")
        target["value_expr_nodes"] -= 1
        module["expr_nodes"] -= 1
        self.rewrite_record(path, measured)
        with self.assertRaisesRegex(CorpusError, "target inventory"):
            summarize(run)

    def test_unregistered_extra_return_is_rejected(self):
        run = self.archived_run()
        (run / "returns/w99-001.json").write_text("{}")
        with self.assertRaisesRegex(CorpusError, "extra or missing"):
            summarize(run)


if __name__ == "__main__":
    unittest.main()
