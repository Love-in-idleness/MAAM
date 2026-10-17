"""Exact finite experiments for the monoid models; no asymptotic claims from a cutoff."""
from itertools import product

from .corpus import CorpusError, natural


def additive_lengths(radius: int, macros: list[int]) -> list[int]:
    natural(radius, "radius")
    for macro in macros:
        natural(macro, "macro", positive=True)
    coins = sorted({1, *(m for m in macros if m <= radius)})
    lengths = [0]*(radius+1)
    for n in range(1, radius+1):
        lengths[n] = 1 + min(lengths[n-c] for c in coins if c <= n)
    return lengths


def coverage(lengths: list[int], budget: int) -> dict:
    natural(budget, "budget")
    if not lengths or lengths[0] != 0:
        raise CorpusError("coverage requires lengths starting at the identity of length zero")
    for radius, length in enumerate(lengths):
        if length > budget:
            return {"budget": budget, "radius": radius-1, "lower_bound": radius-1, "right_censored": False}
    return {"budget": budget, "radius": None, "lower_bound": len(lengths)-1, "right_censored": True}


def place_coverage(budget: int, base=2, dimension=1) -> int:
    """Exact An L1-ball coverage for coordinate-wise powers of the base.

    Minimum macro length is the total base-b digit sum. The smallest L1 norm
    with budget+1 digits fills the cheapest digit positions across coordinates.
    """
    natural(budget, "budget")
    natural(base, "base", positive=True)
    natural(dimension, "dimension", positive=True)
    if base < 2:
        raise CorpusError("base must be at least 2")
    quotient, remainder = divmod(budget+1, dimension*(base-1))
    return dimension*(base**quotient-1)+remainder*base**quotient-1


def free_length(word: str, alphabet: tuple[str, ...], macros: list[str]) -> int:
    if not alphabet or any(not isinstance(c, str) or len(c) != 1 for c in alphabet):
        raise CorpusError("alphabet must contain individual characters")
    symbols = set(alphabet)
    if any(c not in symbols for c in word) or any(not m or any(c not in symbols for c in m) for m in macros):
        raise CorpusError("word and nonempty macros must use only the stated alphabet")
    generators = sorted(symbols | set(macros))
    lengths = [0]+[len(word)+1]*len(word)
    for stop in range(1, len(word)+1):
        lengths[stop] = min(lengths[stop-len(g)]+1 for g in generators
                            if len(g) <= stop and word.startswith(g, stop-len(g)))
    return lengths[-1]


def free_sphere_worst(radius: int, alphabet: tuple[str, ...], macros: list[str]) -> list[int]:
    natural(radius, "radius")
    # Explicit enumeration is deliberately bounded; callers select a feasible radius.
    return [max((free_length("".join(w),alphabet,macros) for w in product(alphabet,repeat=r)), default=0)
            for r in range(radius+1)]
