#!/usr/bin/env python3
"""Run the real Lean ablation, whole-declaration inventories and guard cases."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from maam import CorpusError
from maam.ablation import load_study, measure_attempt, run_study
from maam.migration import save_new, start_session, submit_attempt, task_request

STUDY=ROOT/"experiments/hom_kernel_ablation/study.json"


def controls(study,output):
    cases={}
    loaded=study["loaded"][0]
    session=output/"control-auxiliary"
    start_session(loaded["suite_path"],session,condition="baseline",solver_id="ablation-controls",mode="supplied_reference")
    request=task_request(session,"d01")
    raw=loaded["pools"]["d01"][0]
    result=submit_attempt(session,{"task_id":"d01","request_sha256":request["request_sha256"],
        "proof":raw["proof"]+"\n\ndef unusedHelper (n : Nat) : Nat := n",
        "bridge":"Retain an unused local declaration so the inventory must charge it."})
    measurement=measure_attempt(loaded["frozen"],request,result["artifact"],study["manifest"]["measurement_budget"])
    module=next(m for m in measurement["inventory"]["modules"] if m["module"]=="Proof") if measurement["inventory"] else None
    target=result["audit"]["targets"][0] if result.get("audit") else None
    cases["unused_auxiliary_charged"]={"formal_status":result["status"],"measurement_status":measurement["status"],
        "matched":bool(module and target and any(d["name"]=="Submission.unusedHelper" for d in module["declarations"])
                       and module["expr_nodes"]>target["signature_expr_nodes"]+target["proof_expr_nodes"])}
    with tempfile.TemporaryDirectory() as temp:
        copied=Path(temp)/"attempt"
        shutil.copytree(result["artifact"],copied)
        source=copied/"Proof.lean"
        source.write_text(source.read_text()+"\n")
        try:
            measure_attempt(loaded["frozen"],request,copied,study["manifest"]["measurement_budget"])
        except CorpusError as exc:
            cases["inventory_bound_to_verified_bytes"]={"matched":"unchanged verified proof" in str(exc),"message":str(exc)}
        else:cases["inventory_bound_to_verified_bytes"]={"matched":False}
    loaded=next(v for v in study["loaded"] if v["variant"]["id"]=="definitions")
    full=next(v for v in study["loaded"] if v["variant"]["id"]=="full")
    session=output/"control-removed-lemma"
    start_session(loaded["suite_path"],session,condition="treatment",solver_id="ablation-controls",mode="supplied_reference")
    request=task_request(session,"d01")
    witness=full["pools"]["d01"][1]
    result=submit_attempt(session,{"task_id":"d01","request_sha256":request["request_sha256"],
                                   "proof":witness["proof"],"bridge":witness["bridge"]})
    cases["removed_lemma_unavailable"]={"formal_status":result["status"],"failure":result.get("failure"),
        "matched":result["status"]=="rejected" and "kernel_mul" in result.get("failure",{}).get("message","")}
    return cases


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    parser.add_argument("--workers",type=int,default=2)
    args=parser.parse_args()
    output=Path(args.output).resolve()
    study=load_study(STUDY)
    comparison=run_study(STUDY,output,workers=args.workers)
    cases=controls(study,output)
    verified=sum(v["verified_attempts"] for v in comparison["coverage"].values())
    measured=sum(v["measured_attempts"] for v in comparison["coverage"].values())
    passed=verified==measured==140 and len(comparison["common_measured_tasks"])==20 and all(c["matched"] for c in cases.values())
    save_new(output/"validation.json",{"status":"passed" if passed else "failed","verified_attempts":verified,
        "measured_attempts":measured,"cases":cases,"study_fingerprints":study["fingerprints"]})
    print(json.dumps({"verified":verified,"measured":measured,"controls":cases,
                      "package_costs":comparison["package_costs"],
                      "relations":[{k:p[k] for k in ("left","right","coverage_relation","cost_relation")} for p in comparison["pairs"]]},indent=2),flush=True)
    if not passed:raise SystemExit(1)


if __name__=="__main__":main()
