"""Keep primitive counts exact and never overflow while normalising ratios."""

import math


def integer_summary(n: int) -> dict:
    # Python's decimal conversion limit should not be disabled globally.
    return {"exact": str(n) if n.bit_length() <= 3300 else None,
            "bits": n.bit_length(), "log2": math.log2(n) if n else None}


def ratio(n: int | None, d: int | None) -> dict | None:
    if n is None or d is None or d == 0:
        return None
    log = math.log2(n) - math.log2(d) if n else None
    try:
        value = n / d
    except OverflowError:
        value = None
    if value is not None and not math.isfinite(value):
        value = None
    return {"value": value, "log2": log,
            "numerator": integer_summary(n), "denominator": integer_summary(d)}


def log1p_ratio(r: dict | None) -> float:
    """Natural log(1+n/d), even when n/d is too large for a float."""
    if r is None or r["log2"] is None:
        return 0.0
    x = r["log2"] * math.log(2)
    return max(x, 0) + math.log1p(math.exp(-abs(x)))


def percentiles(values: dict[str, float]) -> dict[str, float]:
    """Midrank on [0,100]; all ties and singleton cohorts get 50."""
    if not values:
        return {}
    if len(values) == 1:
        return {next(iter(values)): 50.0}
    items = sorted(values, key=lambda k: (values[k], k))
    out = {}
    i = 0
    while i < len(items):
        j = i + 1
        while j < len(items) and math.isclose(values[items[j]], values[items[i]],
                                             rel_tol=1e-10, abs_tol=1e-15):
            j += 1
        p = 100 * (i + (j - i - 1) / 2) / (len(items) - 1)
        for k in items[i:j]:
            out[k] = p
        i = j
    return out
