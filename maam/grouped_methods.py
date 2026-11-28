"""Two bounded core-tactic candidates generated solely from a grouped request."""
from pathlib import Path

from .corpus import CorpusError
from . import grouped_search
from .theory import digest

METHODS = ("core_direct", "core_shared_identity")


def generate(request):
    slot = request["slot"]
    if type(slot) is not int or slot < 1:
        raise CorpusError("group method requires a positive request slot")
    if slot > len(METHODS):
        return {"action": "retain", "request_sha256": request["request_sha256"],
                "reason": "The two declared local methods are exhausted; keep prepared witnesses."}
    helpers = ""
    tail = "  first | assumption | rfl"
    if slot == 2:
        helpers = "have reuse (P : Prop) (h : P) : P := h"
        tail = "  apply reuse\n  first | assumption | rfl"
    return {"action": "candidate", "request_sha256": request["request_sha256"],
            "helpers": helpers,
            "proofs": {t["id"]: f"by\n  unfold {t['goal']}\n  intros\n{tail}"
                       for t in request["targets"]},
            "bridge": f"Deterministic {METHODS[slot - 1]}; method source SHA-256 "
                      f"{digest(Path(__file__).read_bytes())}. Lean must verify every original target."}


def run(root, phase, *, lean="lean"):
    initial = grouped_search.report(root)
    remaining = initial["attempt_cap_per_stage"] - len(initial["stages"][phase]["outcomes"])
    decisions = []
    for _ in range(remaining):
        request = grouped_search.request(root, phase)
        response = generate(request)
        decisions.append(grouped_search.submit(root, phase, response, lean=lean))
    return {"schema_version": 1, "status": "local_group_methods_finished", "phase": phase,
            "methods": list(METHODS), "method_sha256": digest(Path(__file__).read_bytes()),
            "provider_calls": 0, "decisions": decisions, "report": grouped_search.report(root),
            "scope": "Two deterministic core-tactic methods on the whole group. "
                     "No model generation or general proof-search completeness."}
