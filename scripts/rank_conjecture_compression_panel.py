"""Rank exact, verified proof portfolios over a frozen Mathlib panel."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

# Support invocation from a checkout without installing the project.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from maam.conjecture_compression import _suite
from maam.corpus import CorpusError
from maam.theory import digest, inside, read_object


def rank_panel(path):
    path = Path(path).resolve()
    spec = read_object(path)
    if type(spec.get("schema_version")) is not int or spec["schema_version"] != 1:
        raise CorpusError("expected compression panel schema_version 1")
    labels = spec["candidate_labels"]
    if not labels or not spec["targets"]:
        raise CorpusError("panel requires candidates and targets")
    results = {key: {} for key in labels}
    assumptions = defaultdict(set)
    evidence, upstream = {}, {}
    revision = toolchain = None
    for target, source in spec["targets"].items():
        suite_path = inside(path.parent, source["suite"], f"{target}.suite")
        suite, _, fingerprints = _suite(suite_path)
        report_path = inside(path.parent, source["report"], f"{target}.report")
        report = read_object(report_path)
        if report.get("status") != "measured" or report.get("fingerprints") != fingerprints:
            raise CorpusError(f"{target}: missing verified report for the frozen sources")
        auditor = report.get("panel_audit", {}).get("compiled_source_sha256", fingerprints["auditor_sha256"])
        if auditor not in source["allowed_auditor_sources"]:
            raise CorpusError(f"{target}: auditor source does not match the frozen panel")
        if set(suite["targets"]) != {target} or report.get("suite_id") != suite["suite_id"]:
            raise CorpusError(f"{target}: report and target do not identify the same suite")
        revision = revision or suite["mathlib_revision"]
        toolchain = toolchain or report["lean_version"]
        if (report["mathlib_revision"] != revision or suite["mathlib_revision"] != revision
                or report["lean_version"] != toolchain):
            raise CorpusError(f"{target}: inconsistent library or Lean version")
        evidence[target] = {"report": source["report"], "sha256": digest(report_path.read_bytes()),
                            "auditor_source_sha256": auditor}
        measured = report["candidates"]
        carry = set(source["carry_original"])
        if (not measured or measured.keys() != suite["candidates"].keys()
                or carry & measured.keys() or (carry | measured.keys()) != labels.keys()):
            raise CorpusError(f"{target}: candidates must match the frozen witness and carry plan")
        original = next(iter(measured.values()))["tasks"][target]["original"]
        upstream[target] = original
        for key in labels:
            if key in carry:
                results[key][target] = {"status": "original_carried", "baseline_tokens": original["proof_module_tokens"],
                                        "retained_tokens": original["proof_module_tokens"], "replacement_tokens": None}
                continue
            candidate = measured[key]
            pair = candidate["tasks"][target]
            if pair["status"] != "verified" or pair["original"] != original:
                raise CorpusError(f"{target}/{key}: inconsistent proof evidence")
            alternative = pair["proof"]
            cost = alternative["assumption_module_tokens"]
            assumptions[key].add((fingerprints["source_sha256"][f"assumption/{key}"], cost))
            before, after = original["proof_module_tokens"], alternative["proof_module_tokens"]
            results[key][target] = {"status": "verified", "baseline_tokens": before,
                                    "retained_tokens": min(before, after), "replacement_tokens": after,
                                    "replacement_body_tokens": alternative["proof_body_tokens"],
                                    "replacement_expression_nodes": alternative["proof_expr_nodes"]}

    baseline = sum(record["proof_module_tokens"] for record in upstream.values())
    ranking = []
    for key, tasks in results.items():
        if len(assumptions[key]) != 1:
            raise CorpusError(f"{key}: require one consistent conjecture statement across its verified witnesses")
        (signature, statement_cost), = assumptions[key]
        retained = sum(task["retained_tokens"] for task in tasks.values())
        ranking.append({"candidate": key, "label": labels[key], "targets": tasks,
                        "assumption_sha256": signature, "statement_tokens": statement_cost,
                        "baseline_tokens": baseline, "retained_proof_tokens": retained,
                        "observed_gross_tokens_saved": baseline - retained,
                        "conditional_net_tokens_saved": baseline - retained - statement_cost,
                        "proof_of_conjecture_tokens": None})
    ranking.sort(key=lambda row: (-row["conditional_net_tokens_saved"], row["candidate"]))
    previous_score = None
    for i, row in enumerate(ranking, 1):
        score = row["conditional_net_tokens_saved"]
        if score != previous_score:
            rank = i
        row["rank"] = rank
        previous_score = score
    return {"schema_version": 1, "panel_id": spec["panel_id"], "panel_sha256": digest(path.read_bytes()),
            "mathlib_revision": revision, "lean_version": toolchain, "target_evidence": evidence,
            "originals": upstream, "ranking": ranking}


def markdown(report):
    targets = list(report["originals"])
    lines = [
        "# MAAM 猜想条件压缩榜 v2 / Conjecture compression v2",
        "",
        "每个分数等于原证明文件总 token 减去选定的证明文件总 token，再减去一次猜想陈述文件的 token。",
        "斜线列按原文件 → 替代文件显示。— 表示该项冻结为保留原证。",
        "",
        "Each score is the original proof portfolio’s token count minus the retained proof portfolio’s tokens "
        "and one charge for the conjecture statement. Each target shows original → alternative. "
        "A dash denotes a frozen decision to carry the original.",
        "",
        "| 名次 / Rank | 猜想 / Conjecture | " + " | ".join(targets) +
        " | 毛节省 / Gross | 陈述 / Statement | 条件净节省 / Net |",
        "| ---: | --- | " + " | ".join("---:" for _ in targets) + " | ---: | ---: | ---: |",
    ]
    for row in report["ranking"]:
        cells = []
        for key in targets:
            task = row["targets"][key]
            after = task["replacement_tokens"] if task["status"] == "verified" else "—"
            cells.append(f"{task['baseline_tokens']} → {after}")
        lines.append(
            f"| {row['rank']} | {row['label']} | {' | '.join(cells)} | "
            f"{row['observed_gross_tokens_saved']} | {row['statement_tokens']} | "
            f"{row['conditional_net_tokens_saved']:+d} |"
        )
    lines += ["", "完整核验和计量 / Full verification and measurement", ""]
    for key, info in report["target_evidence"].items():
        lines.append(f"- [{key} Lean report]({info['report']})")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    args = parser.parse_args()
    try:
        report = rank_panel(args.panel)
    except (CorpusError, OSError, ValueError) as exc:
        parser.error(str(exc))
    print(markdown(report) if args.format == "markdown" else json.dumps(report, ensure_ascii=False, indent=2),
          end="" if args.format == "markdown" else "\n")


if __name__ == "__main__":
    main()
