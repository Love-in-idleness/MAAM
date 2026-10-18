#!/usr/bin/env python3
"""Run the portable skill packager on valid, stale and oversized artifacts."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from maam.migration import start_session, task_request, save_new

def main():
    script=ROOT/"skills/evaluate-theory-package/scripts/pack_submission.py"
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        session=root/"session"
        start_session(ROOT/"experiments/hom_kernel_migration/suite.json",session,
                      condition="treatment",solver_id="packager-check")
        request=task_request(session,"d02")
        save_new(root/"request.json",request)
        (root/"proof.lean").write_text("by\n  intro G H g h f hf x hx\n  exact Theory.kernel_mul (⟨f, hf⟩ : Theory.Hom g h) hx hx\n")
        (root/"bridge.txt").write_text("Bundle the raw function; apply kernel closure twice to the same hypothesis.")
        command=[sys.executable,str(script),"--request",str(root/"request.json"),
                 "--proof",str(root/"proof.lean"),"--bridge",str(root/"bridge.txt"),
                 "--output",str(root/"submission.json")]
        good=subprocess.run(command,capture_output=True,text=True)
        assert good.returncode==0,good.stderr
        response=json.loads((root/"submission.json").read_text())
        assert response["request_sha256"]==request["request_sha256"] and response["task_id"]=="d02"
        again=subprocess.run(command,capture_output=True,text=True)
        assert again.returncode!=0,"must not overwrite an existing submission"
        request["condition"]="baseline"
        (root/"request.json").write_text(json.dumps(request))
        stale=subprocess.run(command[:-1]+[str(root/"stale.json")],capture_output=True,text=True)
        assert stale.returncode!=0 and "request fingerprint mismatch" in stale.stderr
        save_new(root/"request-good.json",task_request(session,"d02"))
        (root/"proof.lean").write_text("x"*32769)
        oversize=command.copy()
        oversize[3]=str(root/"request-good.json")
        oversize[-1]=str(root/"oversize.json")
        bad=subprocess.run(oversize,capture_output=True,text=True)
        assert bad.returncode!=0 and "response-size budget" in bad.stderr
    print("Skill packager: valid request, no overwrite, stale request and response-size checks passed.")

if __name__=="__main__":
    main()
