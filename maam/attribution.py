"""Source-cost bookkeeping; observed differences alone do not certify causality."""
from .corpus import CorpusError


def source_attribution(*, historical, prepared, control, treatment, package):
    """Compare retained portfolios for identical goals and one frozen metric.

    The caller supplies verified costs including each arm's new shared helpers;
    treatment excludes only the separately charged whole package. Unknown is None.
    """
    values = (historical, prepared, control, treatment, package)
    if any(x is not None and (type(x) is not int or x < 0) for x in values):
        raise CorpusError("source costs must be nonnegative integers or unknown")
    for before, after in ((historical, prepared), (prepared, control), (prepared, treatment)):
        if before is not None and after is not None and after > before:
            raise CorpusError("retained proof portfolios cannot discard a cheaper incumbent")

    def difference(*terms):
        return terms[0] - sum(terms[1:]) if all(x is not None for x in terms) else None

    cleanup = difference(historical, prepared)
    continuing = difference(prepared, control)
    package_net = difference(control, treatment, package)
    historical_net = difference(historical, treatment, package)
    complete = all(x is not None for x in values)
    return {"status": "complete_bookkeeping" if complete else "incomplete_cost_evidence",
            "unit": "source_tokens",
            "historical_net_saving": historical_net,
            "old_tool_preparation_saving": cleanup,
            "continued_old_tool_search_saving": continuing,
            "package_associated_net_difference": package_net,
            "decomposition_total": cleanup + continuing + package_net if complete else None,
            "identity_verified": historical_net == cleanup + continuing + package_net if complete else None,
            "causal_effect_established": False, "global_minimum_established": False,
            "scope": "Cost identity on the same goals and fixed metric; verified witnesses, "
                     "semantic compatibility and matched search must be established separately. "
                     "New-only solved goals are outside this compression comparison."}
