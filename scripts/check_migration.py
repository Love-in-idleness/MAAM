#!/usr/bin/env python3
"""Actual Lean replay of 40 calibration witnesses and protocol rejection cases."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maam import CorpusError
from maam.migration import (start_session, task_request, submit_attempt, session_report,
                           compare_sessions, save_new, load_suite)
from maam.theory import digest

SUITE = ROOT/"experiments/hom_kernel_migration/suite.json"


def payload(session, task, witness):
    return {"task_id": task, "request_sha256": task_request(session, task)["request_sha256"], **witness}


def negative_cases(output, references):
    cases = {}
    def fresh(label, condition="baseline"):
        session=output/("negative-"+label)
        start_session(SUITE,session,condition=condition,solver_id="negative-check",mode="supplied_reference")
        return session
    session=fresh("sorry")
    witness={**references["d01"]["baseline"],"proof":"by\n  sorry"}
    result=submit_attempt(session,payload(session,"d01",witness))
    cases["sorry"]={"status":result["status"],"failure":result.get("failure"),
                    "matched":result["status"]=="rejected" and "sorryAx" in result.get("failure",{}).get("message","")}
    session=fresh("unused-axiom")
    witness={**references["d01"]["baseline"],"proof":references["d01"]["baseline"]["proof"]+"\n\naxiom unused : False"}
    result=submit_attempt(session,payload(session,"d01",witness))
    cases["unused_axiom"]={"status":result["status"],"failure":result.get("failure"),
                          "matched":result["status"]=="rejected" and "forbidden axiom" in result.get("failure",{}).get("message","")}
    session=fresh("candidate-leak")
    result=submit_attempt(session,payload(session,"d01",references["d01"]["treatment"]))
    cases["candidate_in_baseline"]={"status":result["status"],"failure":result.get("failure"),
                                    "matched":result["status"]=="rejected" and result.get("failure",{}).get("stage")=="compile:Proof"}
    session=fresh("wrong-target")
    result=submit_attempt(session,payload(session,"d01",{"proof":"by\n  exact True.intro","bridge":"wrong proposition"}))
    cases["wrong_target"]={"status":result["status"],"failure":result.get("failure"),
                          "matched":result["status"]=="rejected"}
    # All failed Lean checks consume their slots; a fourth proof never reaches Lean.
    for _ in range(2):
        submit_attempt(session,payload(session,"d01",{"proof":"by\n  exact True.intro","bridge":"repeat failure"}))
    try:
        submit_attempt(session,payload(session,"d01",references["d01"]["baseline"]))
    except CorpusError as exc:
        cases["attempt_cap"]={"status":"rejected","message":str(exc),"matched":"budget exhausted" in str(exc)}
    else:
        cases["attempt_cap"]={"status":"unexpected_acceptance","matched":False}
    session=fresh("cross-condition","treatment")
    other=output/"baseline"
    try:
        submit_attempt(session,payload(other,"d01",references["d01"]["baseline"]))
    except CorpusError as exc:
        cases["cross_condition_request"]={"status":"rejected","message":str(exc),"matched":"different task, condition" in str(exc)}
    else:
        cases["cross_condition_request"]={"status":"unexpected_acceptance","matched":False}
    return cases


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    output=Path(args.output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    reference_path=SUITE.parent/"reference_proofs.json"
    references=json.loads(reference_path.read_text())
    frozen=load_suite(SUITE)
    failures=[]
    for condition in ("baseline","treatment"):
        session=output/condition
        start_session(SUITE,session,condition=condition,solver_id=references["solver_id"],mode="supplied_reference")
        for task in frozen["manifest"]["tasks"]:
            result=submit_attempt(session,payload(session,task["id"],references["tasks"][task["id"]][condition]))
            print(condition,task["id"],result["status"],flush=True)
            if result["status"]!="verified":
                failures.append({"condition":condition,"task":task["id"],"failure":result.get("failure")})
        save_new(output/(condition+"-summary.json"),session_report(session))
    comparison=compare_sessions(output/"baseline",output/"treatment")
    comparison["reference_provenance"]={
        "reference_proofs_sha256":digest(reference_path.read_bytes()),
        "runner_sha256":digest(Path(__file__).read_bytes()),
        "scope":"public supplied calibration witnesses; not autonomous search or blind evaluation"}
    save_new(output/"comparison.json",comparison)
    cases=negative_cases(output,references["tasks"])
    save_new(output/"negative.json",{"schema_version":1,"status":"passed" if all(c["matched"] for c in cases.values()) else "failed",
                                    "fingerprints":frozen["fingerprints"],"cases":cases})
    for case,value in cases.items():
        print("negative",case,value["matched"],flush=True)
    save_new(output/"verification.json",{"status":"passed" if not failures and all(c["matched"] for c in cases.values()) else "failed",
                                       "verified_witnesses":40-len(failures),"failures":failures})
    if failures or not all(c["matched"] for c in cases.values()):
        print(json.dumps({"failures":failures,"cases":cases},indent=2),file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(comparison["common_task_source_ledger"],indent=2))


if __name__=="__main__":
    main()
