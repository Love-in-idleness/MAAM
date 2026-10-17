"""Read an actual fixed-corpus metric index without loading the full graph."""
import json
import math
from pathlib import Path
import sqlite3
from urllib.parse import quote

from .corpus import CorpusError


def score_index(path: str, name: str) -> dict:
    location = Path(path).resolve()
    try:
        db = sqlite3.connect("file:"+quote(str(location))+"?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM metrics WHERE name = ?", (name,)).fetchone()
        meta = db.execute("SELECT value FROM metadata WHERE key = 'summary'").fetchone()
        db.close()
    except sqlite3.Error as exc:
        raise CorpusError(f"cannot read the metric index: {exc}") from exc
    if row is None:
        raise CorpusError(f"unknown indexed declaration: {name}")
    if meta is None:
        raise CorpusError("the index has no provenance metadata")
    data = dict(row)
    w = data["signature_references"]+data["body_references"]
    data["I0_reference"] = data["body_references"]/data["signature_references"] if data["signature_references"] else None
    data["T0_reference_log2"] = data["unwrapped_log2"]-math.log2(w) if w else None
    data["T0_source_log2"] = (data["unwrapped_log2"]-math.log2(data["wrapped_source"])
                               if data["wrapped_source"] and data["wrapped_source"] > 0 else None)
    data["score"] = data["score_reference"]
    return {"status": "indexed_metrics", "assessment": data,
            "metadata": json.loads(meta[0]),
            "score_kind": "reference-basis I1 percentile in the fixed exported corpus",
            "notes": ["Source-token totals are reported separately; a source-level proof/signature split is not inferred.",
                      "Cyclic-component expansion is a condensed-graph convention, not a finite expansion of a recursive program.",
                      "Scores are research heuristics, not human-interest calibration."]}
