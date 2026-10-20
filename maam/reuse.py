"""Optional source shortening over already verified, compatible proof records."""
from .corpus import CorpusError


def retained_portfolio(originals, alternatives, package_source_tokens):
    """Keep original artifacts in their original imports; never force a migration.

    Callers must first verify the same goals/foundation and each witness. This
    selects an evidence portfolio, not a jointly importable Lean library.
    """
    def length(value):
        if value is not None and (type(value) is not int or value < 0):
            raise CorpusError("source costs must be nonnegative integers or unknown")
        return value

    length(package_source_tokens)
    if set(originals) != set(alternatives) or any(not isinstance(k, str) or not k for k in originals):
        raise CorpusError("proof pools must cover the same named goals")
    rows, old_costs, chosen_old_costs, new_costs = [], [], [], []
    for task, old in originals.items():
        new = alternatives[task]
        before = length(old["proof_source_tokens"]) if old is not None else None
        after = length(new["proof_source_tokens"]) if new is not None else None
        replace = old is not None and new is not None and before is not None and after is not None and after < before
        selected = new if replace or old is None else old
        action = ("replace_with_shorter" if replace else "retain_original" if old is not None
                  else "newly_solved" if new is not None else "unobserved")
        selected_cost = length(selected["proof_source_tokens"]) if selected is not None else None
        rows.append({"task_id": task, "action": action,
                     "selected_origin": "alternative" if replace or (old is None and new is not None)
                     else "original" if old is not None else None,
                     "selected": dict(selected) if selected is not None else None,
                     "original_source_tokens": before, "alternative_source_tokens": after})
        if old is not None:
            old_costs.append(before)
            chosen_old_costs.append(selected_cost)
        elif new is not None:
            new_costs.append(selected_cost)

    def known_total(values):
        return sum(values) if values and all(v is not None for v in values) else None

    before, after = known_total(old_costs), known_total(chosen_old_costs)
    gross = before - after if before is not None and after is not None else None
    total = after + package_source_tokens if after is not None and package_source_tokens is not None else None
    return {"status": "derived_retained_proof_portfolio", "selection_metric": "full_proof_module_source_tokens",
            "replacement_rule": "verified and strictly shorter; ties and unknown lengths retain original",
            "tasks": rows,
            "coverage": {"original": [r["task_id"] for r in rows if r["action"] in ("retain_original", "replace_with_shorter")],
                         "retained": [r["task_id"] for r in rows if r["selected"] is not None],
                         "newly_solved": [r["task_id"] for r in rows if r["action"] == "newly_solved"]},
            "original_goal_source_ledger": {"baseline_tokens": before,
                "selected_proof_tokens": after, "gross_tokens_saved": gross,
                "package_tokens_charged_once": package_source_tokens,
                "selected_including_package_tokens": total,
                "net_tokens_saved": gross - package_source_tokens if gross is not None and package_source_tokens is not None else None},
            "new_goal_proof_tokens": known_total(new_costs),
            "scope": "Already verified same-goal witnesses only; original import contexts retained. "
                "New-only goals are outside compression comparisons; inheritance is not model generation success. "
                "The full package is charged once even when no replacement improves a proof."}
