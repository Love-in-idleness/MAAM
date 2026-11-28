"""Measure frozen complete source portfolios before and after a theory package.

Each route supplies every target. Selection is exact over those finite routes
only. Formal correctness and the search information boundary are external.
"""
import bz2
from pathlib import Path
import zlib

from .attribution import portfolio_attribution
from .corpus import CorpusError
from .migration import canonical
from .theory import digest, inside, names, nonempty_string, read_object

METRICS = ("source_utf8_bytes", "zlib_9_bytes", "bzip2_9_bytes")
STAGES = ("historical", "prepared", "control", "treatment")


def measure_sources(sources):
    """Match the immutable archived reference's joint encoding and round trips."""
    payload = canonical({name: source.decode("utf-8") for name, source in sources.items()})
    compressed = zlib.compress(payload, level=9, wbits=15)
    diagnostic = bz2.compress(payload, compresslevel=9)
    if zlib.decompress(compressed) != payload or bz2.decompress(diagnostic) != payload:
        raise CorpusError("joint source encoding failed a byte-exact round trip")
    return {"source_utf8_bytes": sum(map(len, sources.values())),
            "serialized_utf8_bytes": len(payload),
            "zlib_9_bytes": len(compressed), "bzip2_9_bytes": len(diagnostic),
            "payload_sha256": digest(payload), "roundtrip_verified": True}


def load_study(path):
    path = Path(path).resolve()
    data = read_object(path)
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise CorpusError("expected precompression schema_version 1")
    if data.get("phase") != "precompression_source_portfolios":
        raise CorpusError("expected precompression_source_portfolios phase")
    nonempty_string(data.get("study_id"), "study_id")
    targets = names(data.get("targets"), "targets")
    background = names(data.get("background_modules"), "background_modules")
    candidate = data.get("candidate")
    if not isinstance(candidate, dict) or set(candidate) != {"id", "modules"}:
        raise CorpusError("candidate requires id and modules")
    nonempty_string(candidate["id"], "candidate id")
    package = names(candidate["modules"], "candidate modules")
    if set(background) & set(package):
        raise CorpusError("new candidate modules cannot be free background")
    descriptors = data.get("sources")
    if not isinstance(descriptors, dict) or not descriptors:
        raise CorpusError("sources must map module names to frozen files")
    names(list(descriptors), "source modules")
    blobs, hashes = {}, {}
    for module, descriptor in descriptors.items():
        if not isinstance(descriptor, dict) or set(descriptor) != {"path", "sha256"}:
            raise CorpusError("source requires relative path and sha256")
        source = inside(path.parent, descriptor["path"], module).read_bytes()
        if descriptor["sha256"] != digest(source):
            raise CorpusError(f"source fingerprint mismatch: {module}")
        try:
            source.decode("utf-8")
        except UnicodeError as exc:
            raise CorpusError(f"source must be UTF-8: {module}") from exc
        blobs[module], hashes[module] = source, digest(source)
    if not set(background + package) <= set(blobs):
        raise CorpusError("background or package source is missing")
    routes = data.get("routes")
    if not isinstance(routes, list) or not routes:
        raise CorpusError("routes must be nonempty")
    ids, used = set(), set(background + package)
    for route in routes:
        if not isinstance(route, dict) or set(route) != {"id", "stage", "modules", "targets"}:
            raise CorpusError("route requires id, stage, modules and targets")
        route_id = nonempty_string(route["id"], "route id")
        if route_id in ids:
            raise CorpusError("duplicate route id")
        ids.add(route_id)
        if not isinstance(route["stage"], str) or route["stage"] not in STAGES:
            raise CorpusError("invalid route stage")
        modules = names(route["modules"], "route modules")
        if not set(modules) <= set(blobs):
            raise CorpusError(f"unknown route source: {route_id}")
        if set(modules) & set(background):
            raise CorpusError("route modules must exclude the shared background")
        if set(names(route["targets"], "route targets")) != set(targets):
            raise CorpusError("every route must declare coverage of all fixed targets")
        used.update(modules)
    if used != set(blobs):
        raise CorpusError("source table contains unused modules")
    if not any(r["stage"] == "historical" for r in routes):
        raise CorpusError("a historical incumbent is required")
    return {"manifest": data, "blobs": blobs,
            "fingerprints": {"study_sha256": digest(path.read_bytes()),
                "source_sha256": hashes,
                "evaluator_sha256": digest(Path(__file__).read_bytes()),
                "attribution_sha256": digest(Path(__file__).with_name("attribution.py").read_bytes()),
                "serialization_sha256": digest(Path(__file__).with_name("migration.py").read_bytes())}}


def compare_study(path):
    frozen = load_study(path)
    data, blobs = frozen["manifest"], frozen["blobs"]
    package = set(data["candidate"]["modules"])
    measured = []
    for route in data["routes"]:
        modules = set(route["modules"])
        # Using part of the named package pays the whole cost, including control
        # rediscovery. A trimmed independently constructed package has its own ID.
        if modules & package:
            modules |= package
        measures = {}
        for mode, charged in (("complete", modules), ("mandatory", modules | package),
                              ("installed", modules - package)):
            measures[mode] = {"charged_modules": sorted(charged),
                **measure_sources({m: blobs[m] for m in charged})}
        measured.append({"id": route["id"], "stage": route["stage"], "costs": measures})
    available = {"historical": {"historical"}, "prepared": {"historical", "prepared"},
                 "control": {"historical", "prepared", "control"},
                 "treatment": {"historical", "prepared", "treatment"}}

    def select(stage, metric, mode="complete"):
        eligible = [r for r in measured if r["stage"] in available[stage]]
        best = min(eligible, key=lambda r: (r["costs"][mode][metric], r["id"]))
        return {"route_id": best["id"], "cost": best["costs"][mode][metric],
                "charged_modules": best["costs"][mode]["charged_modules"],
                "payload_sha256": best["costs"][mode]["payload_sha256"]}

    metrics = {}
    for metric in METRICS:
        selected = {s: select(s, metric) for s in STAGES}
        costs = {s: r["cost"] for s, r in selected.items()}
        required = select("treatment", metric, "mandatory")
        installed = select("treatment", metric, "installed")
        metrics[metric] = {"optional_adoption": {"selected": selected,
                "attribution": portfolio_attribution(**costs, unit=metric)},
            "mandatory_adoption": {"selected": required,
                "attribution": portfolio_attribution(**{**costs, "treatment": required["cost"]},
                                                     unit=metric, retain_prepared=False)},
            "installed_reuse": {"selected": installed,
                "control_cost": costs["control"],
                "marginal_cost_difference": costs["control"] - installed["cost"],
                "background": "candidate already installed and paid for outside this decision"}}
    return {"schema_version": 1, "status": "measured_source_portfolios",
            "study_id": data["study_id"], "candidate": data["candidate"],
            "targets": data["targets"], "background_modules": data["background_modules"],
            "fingerprints": frozen["fingerprints"], "routes": measured, "metrics": metrics,
            "formal_verification": "not_run_by_source_measurer",
            "goal_coverage": "declared_by_manifest; requires independent formal verification",
            "search_executed": False, "information_separation_established": False,
            "baseline_search_complete": False, "package_attribution_ready": False,
            "causal_effect_established": False, "global_minimum_established": False,
            "selection_scope": "exact over supplied complete routes for each metric and mode",
            "accounting_scope": "new source modules jointly encoded once per route; "
                "common background bytes excluded, import lines retained; dependencies and "
                "automation must be listed by the caller and audited externally"}
