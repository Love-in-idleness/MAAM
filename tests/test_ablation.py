"""Accounting and experiment controls, independent of a local Lean install."""
import copy
from itertools import product
import json
from pathlib import Path
import random
import shutil
import tempfile
import unittest

from maam import CorpusError
from maam.ablation import (cost, frontier_relation, load_study, package_uses,
                           pareto, portfolio, validate_module)
from maam.theory import digest

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT/"experiments/hom_kernel_ablation/study.json"


class AblationTests(unittest.TestCase):
    def copy_study(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)/"study"
        shutil.copytree(STUDY.parent, root)
        return root

    def save(self, path, data):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n")

    def refresh_descriptor(self, root, variant_id, field):
        data = json.loads((root/"study.json").read_text())
        item = next(v for v in data["variants"] if v["id"] == variant_id)[field]
        item["sha256"] = digest((root/item["path"]).read_bytes())
        self.save(root/"study.json", data)

    def test_actual_study_retains_raw_proofs_and_candidate_versions(self):
        study = load_study(STUDY)
        self.assertEqual(len(study["shared"]["tasks"]), 20)
        self.assertEqual([v["variant"]["id"] for v in study["loaded"]], ["baseline","naming","definitions","full"])
        full = study["loaded"][-1]["frozen"]["blobs"]["Candidate"]
        self.assertEqual(full,(ROOT/"experiments/hom_kernel_migration/Candidate.lean").read_bytes())
        definitions = study["loaded"][-2]["frozen"]["blobs"]["Candidate"]
        self.assertNotIn(b"theorem kernel_mul",definitions)
        self.assertEqual(sum(len(p) for v in study["loaded"] for p in v["pools"].values()),140)

    def test_unfrozen_source_is_rejected(self):
        root = self.copy_study()
        path = root/"candidates/naming.lean"
        path.write_text(path.read_text()+"\n")
        with self.assertRaisesRegex(CorpusError,"fingerprint mismatch"):
            load_study(root/"study.json")

    def test_refrozen_changed_goal_cannot_enter_an_ablation(self):
        root = self.copy_study()
        path = root/"suite-definitions.json"
        data = json.loads(path.read_text())
        data["tasks"][0]["goal"] = "Tasks.differentGoal"
        self.save(path,data)
        self.refresh_descriptor(root,"definitions","suite")
        with self.assertRaisesRegex(CorpusError,"identical foundation, goals"):
            load_study(root/"study.json")

    def test_raw_fallback_cannot_be_removed(self):
        root = self.copy_study()
        path = root/"witnesses/definitions.json"
        data = json.loads(path.read_text())
        data["tasks"]["d01"] = data["tasks"]["d01"][1:]
        self.save(path,data)
        self.refresh_descriptor(root,"definitions","witnesses")
        with self.assertRaisesRegex(CorpusError,"retain all raw baseline proofs"):
            load_study(root/"study.json")

    def test_different_submission_budget_is_rejected(self):
        root = self.copy_study()
        path = root/"suite-definitions.json"
        data = json.loads(path.read_text())
        data["budget"]["max_attempts_per_task"] = 4
        self.save(path,data)
        self.refresh_descriptor(root,"definitions","suite")
        with self.assertRaisesRegex(CorpusError,"budgets"):
            load_study(root/"study.json")

    def test_over_budget_pool_cannot_be_refrozen(self):
        root = self.copy_study()
        path = root/"witnesses/naming.json"
        data = json.loads(path.read_text())
        data["tasks"]["d01"] *= 2
        self.save(path,data)
        self.refresh_descriptor(root,"naming","witnesses")
        with self.assertRaisesRegex(CorpusError,"attempt cap"):
            load_study(root/"study.json")

    def test_pareto_keeps_tradeoffs_and_collapses_equal_costs(self):
        points = [cost(1,10),cost(10,1),cost(5,5),cost(6,6),cost(5,5)]
        self.assertEqual(pareto(points),[cost(1,10),cost(5,5),cost(10,1)])

    def test_dynamic_program_matches_exhaustive_portfolios(self):
        rng = random.Random(449)
        for _ in range(30):
            rows = [{"id":str(i),"attempts":[{"attempt":j,"cost":cost(rng.randrange(1,20),rng.randrange(1,20))}
                                            for j in range(3)]} for i in range(4)]
            fixed = cost(7,11)
            observed = portfolio(rows,fixed,[r["id"] for r in rows],1000)
            exhaustive = pareto([cost(7+sum(a["cost"]["source_tokens"] for a in chosen),
                                     11+sum(a["cost"]["expr_nodes"] for a in chosen))
                                 for chosen in product(*(r["attempts"] for r in rows))])
            self.assertEqual([{k:p[k] for k in ("source_tokens","expr_nodes")} for p in observed["points"]],exhaustive)

    def test_package_is_charged_once(self):
        rows = [{"id":tid,"attempts":[{"attempt":1,"cost":cost(10,20)}]} for tid in ("a","b")]
        point = portfolio(rows,cost(100,200),["a","b"],10)["points"][0]
        self.assertEqual((point["source_tokens"],point["expr_nodes"]),(120,240))

    def test_frontier_limit_never_silently_truncates(self):
        rows = [{"id":"a","attempts":[{"attempt":1,"cost":cost(1,10)},{"attempt":2,"cost":cost(10,1)}]}]
        limited = portfolio(rows,cost(0,0),["a"],1)
        self.assertEqual(limited["status"],"frontier_budget_exhausted")
        self.assertEqual(limited["points"],[])
        exact = portfolio(rows,cost(0,0),["a"],10)
        self.assertEqual(frontier_relation(limited,exact),"undetermined")

    def test_no_common_tasks_cannot_become_zero_cost_success(self):
        empty = portfolio([],None,[],10)
        self.assertEqual(empty,{"status":"no_common_tasks","points":[]})
        self.assertEqual(frontier_relation(empty,empty),"undetermined")

    def test_frontier_order_checks_sets_not_separate_coordinate_minima(self):
        def front(points):return {"status":"exact_finite_portfolio","points":[cost(*p) for p in points]}
        a,b,c = front([(1,10),(10,1)]),front([(5,5)]),front([(2,11),(11,2)])
        self.assertEqual(frontier_relation(a,b),"incomparable")
        self.assertEqual(frontier_relation(a,c),"left_dominates")
        self.assertEqual(frontier_relation(c,a),"right_dominates")
        self.assertEqual(frontier_relation(a,copy.deepcopy(a)),"equivalent")

    def test_auxiliary_declarations_are_counted_and_usage_is_transitive(self):
        def decl(name,refs,signature=2,value=3):
            return {"name":name,"direct_dependencies":refs,"signature_expr_nodes":signature,"value_expr_nodes":value}
        proof = {"module":"Proof","declaration_count":3,"expr_nodes":15,"declarations":[
            decl("Submission.solve",["Submission.helper"]),decl("Submission.helper",["Theory.lemma"]),decl("Submission.unused",[])]}
        package = {"module":"Candidate","declaration_count":1,"expr_nodes":5,"declarations":[decl("Theory.lemma",[])]}
        validate_module(proof)
        self.assertEqual(package_uses(proof,[package]),["Theory.lemma"])
        proof["expr_nodes"] = 10
        with self.assertRaisesRegex(CorpusError,"total is inconsistent"):
            validate_module(proof)

    def test_invalid_costs_and_duplicate_declarations_are_rejected(self):
        with self.assertRaises(CorpusError):cost(-1,3)
        with self.assertRaises(CorpusError):cost(True,3)
        with self.assertRaisesRegex(CorpusError,"duplicated"):
            validate_module({"declarations":[{"name":"same"},{"name":"same"}]})


if __name__=="__main__":
    unittest.main()
