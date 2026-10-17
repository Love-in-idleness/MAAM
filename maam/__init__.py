"""MAAM: corpus-relative, evidence-bearing interest metrics."""

from .calculator import Calculator, direct_metrics
from .corpus import Corpus, CorpusError
from .proofs import ProofSystem

__all__ = ["Calculator", "Corpus", "CorpusError", "ProofSystem", "direct_metrics"]
__version__ = "0.1.0"
