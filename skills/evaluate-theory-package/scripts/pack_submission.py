#!/usr/bin/env python3
"""Package one task-local Lean term without importing MAAM or executing Lean."""
import argparse
import hashlib
import json
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("request","proof","bridge","output"):
        parser.add_argument("--"+name,required=True,type=Path)
    args=parser.parse_args()
    request=json.loads(args.request.read_text(encoding="utf-8"))
    unsigned={k:v for k,v in request.items() if k!="request_sha256"}
    if request.get("request_sha256")!=sha(canonical(unsigned)):
        parser.error("request fingerprint mismatch")
    for source in request["sources"]:
        if sha(source["content"].encode())!=source["sha256"]:
            parser.error("source fingerprint mismatch: "+source["module"])
    proof=args.proof.read_text(encoding="utf-8")
    bridge=args.bridge.read_text(encoding="utf-8").strip()
    if not proof.strip() or not bridge:
        parser.error("proof and bridge must be nonempty")
    if len(proof.encode())>request["budget"]["max_proof_bytes"]:
        parser.error("proof exceeds the frozen response-size budget")
    submission={"task_id":request["task"]["id"],"request_sha256":request["request_sha256"],
                "proof":proof,"bridge":bridge}
    with args.output.open("x",encoding="utf-8") as out:
        out.write(json.dumps(submission,ensure_ascii=False,indent=2)+"\n")
    print(str(args.output))


if __name__=="__main__":
    main()
