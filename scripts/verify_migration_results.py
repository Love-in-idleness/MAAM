#!/usr/bin/env python3
"""Replay archived accounting and fingerprints; fresh Lean runs are separate."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from maam.migration import load_suite
from maam.theory import digest


def read(path):
    return json.loads(path.read_text())


def check_pair(comparison,left,right,tasks,package_tokens):
    assert comparison["held_out_evaluation"] is False and comparison["training_eligible"] is False
    assert comparison["generation_budget_verified"] is False
    assert left["condition"]=="baseline" and right["condition"]=="treatment"
    assert left["fingerprints"]==right["fingerprints"]==comparison["fingerprints"]
    assert left["budget"]==right["budget"]==comparison["budget"]
    assert left["solver"]==right["solver"]==comparison["solver"]
    task_ids=[t["id"] for t in tasks]
    sets=[]
    for report in (left,right):
        assert [t["id"] for t in report["tasks"]]==task_ids
        solved=set()
        for task,row in zip(tasks,report["tasks"]):
            assert all(row[k]==task[k] for k in ("id","split","goal","module","family"))
            assert len(row["attempts"])<=report["budget"]["max_attempts_per_task"]
            chosen=row["selected"]
            if chosen is None:
                assert row["status"]=="not_observed_solved"
                continue
            assert row["status"]=="verified"
            target=chosen["target"]
            assert target["name"]=="Submission.solve" and target["expected"]==task["goal"]
            assert target["goal_preserved"] is True
            src=target["source"]
            assert src["declaration_tokens"]==src["signature_tokens"]+src["body_tokens"]+1
            assert chosen["proof_source_tokens"]>=src["declaration_tokens"]
            assert chosen["package_source_tokens"]==(0 if report["condition"]=="baseline" else package_tokens)
            solved.add(task["id"])
        sets.append(solved)
    assert comparison["coverage"]["baseline"]==sorted(sets[0])
    assert comparison["coverage"]["treatment"]==sorted(sets[1])
    common=sets[0]&sets[1]
    ledger=comparison["common_task_source_ledger"]
    assert ledger["task_ids"]==sorted(common)
    costs=[sum(t["selected"]["proof_source_tokens"] for t in r["tasks"] if t["id"] in common)
           for r in (left,right)]
    assert ledger["baseline_tokens"]==(costs[0] if common else None)
    assert ledger["treatment_including_package_tokens"]==(costs[1]+package_tokens if common else None)
    assert ledger["package_tokens_charged_once"]==(package_tokens if common else None)
    assert ledger["net_tokens_saved"]==(costs[0]-costs[1]-package_tokens if common else None)
    for row,a,b in zip(comparison["tasks"],left["tasks"],right["tasks"]):
        assert row["id"]==a["id"]==b["id"]
        before,after=a["selected"],b["selected"]
        assert row["local_body_tokens_saved"]==(before["target"]["source"]["body_tokens"]-after["target"]["source"]["body_tokens"] if before and after else None)
        assert row["local_expr_nodes_saved"]==(before["target"]["proof_expr_nodes"]-after["target"]["proof_expr_nodes"] if before and after else None)


def verify():
    folder=ROOT/"results/migration"
    receipt=read(folder/"validation.json")
    assert receipt["status"]=="verified" and receipt["workflow_conclusion"]=="success"
    for filename,expected in receipt["reports_sha256"].items():
        assert digest((folder/filename).read_bytes())==expected,filename
    frozen=load_suite(ROOT/"experiments/hom_kernel_migration/suite.json")
    comparison=read(folder/"comparison.json")
    assert comparison["fingerprints"]==frozen["fingerprints"]
    provenance=comparison["reference_provenance"]
    assert provenance["reference_proofs_sha256"]==digest((ROOT/"experiments/hom_kernel_migration/reference_proofs.json").read_bytes())
    assert provenance["runner_sha256"]==digest((ROOT/"scripts/check_migration.py").read_bytes())
    for condition in ("baseline","treatment"):
        p=comparison["provenance"][condition]
        assert p["code_commit"]==receipt["implementation_commit"]
        assert p["workflow_run_id"]==str(receipt["workflow_run_id"])
    # The unchanged M1 checker measured this exact byte-identical candidate.
    m1=read(ROOT/"results/theory-package-reference.json")
    assert m1["fingerprints"]["checker_sha256"]==frozen["fingerprints"]["checker_sha256"]
    assert m1["fingerprints"]["source_sha256"]["Candidate"]==frozen["fingerprints"]["source_sha256"]["Candidate"]
    package_tokens=sum(s["source_tokens"] for s in m1["audits"]["treatment"]["sources"] if s["module"]=="Candidate")
    check_pair(comparison,read(folder/"baseline-summary.json"),read(folder/"treatment-summary.json"),frozen["manifest"]["tasks"],package_tokens)
    assert len(comparison["coverage"]["baseline"])==len(comparison["coverage"]["treatment"])==20
    assert comparison["solver"]["mode"]=="supplied_reference"
    forward=read(folder/"forward-comparison.json")
    check_pair(forward,read(folder/"forward-baseline-summary.json"),read(folder/"forward-treatment-summary.json"),frozen["manifest"]["tasks"],package_tokens)
    assert forward["worker_artifacts_sha256"]==digest((ROOT/"experiments/hom_kernel_migration/skill_forward.json").read_bytes())
    assert forward["solver"]["mode"]=="interactive_agent"
    assert forward["coverage"]["baseline"]==forward["coverage"]["treatment"]==["d02"]
    negative=read(folder/"negative.json")
    assert negative["fingerprints"]==frozen["fingerprints"]
    assert negative["status"]=="passed" and len(negative["cases"])==receipt["negative_cases"]==6
    assert all(case["matched"] for case in negative["cases"].values())
    verified=read(folder/"verification.json")
    assert verified["status"]=="passed" and verified["verified_reference_witnesses"]==receipt["verified_reference_witnesses"]==40
    assert len(verified["forward_workers"])==receipt["verified_skill_worker_witnesses"]==2
    assert all(row["status"]=="verified" for row in verified["forward_workers"])
    print("M2 archived fingerprints, 40 reference witnesses, 2 skill-worker witnesses and accounting replayed.")


if __name__=="__main__":
    verify()
