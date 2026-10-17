"""A dependency-free command line calculator."""

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .calculator import Calculator, direct_metrics
from .corpus import Corpus, CorpusError
from .proofs import ProofSystem


def parser():
    root = argparse.ArgumentParser(description="MAAM: mathematical-interest metrics / 命题数学兴趣指标")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("score", "rank", "query"):
        p = commands.add_parser(name)
        p.add_argument("--corpus", required=True)
        p.add_argument("--alpha", type=float, default=0.85, help="dependency walk probability")
        p.add_argument("--beta", type=float, default=0.5, help="T0 weight in J0; I0 weight is 1-beta")
        p.add_argument("--format", choices=("json", "text"), default="json")
        p.add_argument("--output", help="write the report to a new file")
        if name == "score":
            p.add_argument("--name", required=True, help="formal declaration name")
        elif name == "query":
            p.add_argument("--statement", required=True, help="exact statement stored in the corpus")
        else:
            p.add_argument("--limit", type=int)
    p = commands.add_parser("metrics", help="calculate T0/I0 from four measured lengths")
    p.add_argument("--signature-wrapped", type=int, required=True)
    p.add_argument("--body-wrapped", type=int)
    p.add_argument("--signature-unwrapped", type=int)
    p.add_argument("--body-unwrapped", type=int)
    p = commands.add_parser("validate")
    p.add_argument("corpus")
    p = commands.add_parser("efficiency", help="finite hypergraph minimum proof efficiency")
    p.add_argument("--system", required=True)
    p.add_argument("--name", required=True)
    p = commands.add_parser("reuse", help="amortised shortcut savings (MAAM extension)")
    p.add_argument("--system", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--goal", action="append", required=True)
    p = commands.add_parser("export-lean", help="export declarations from an existing Lean project")
    p.add_argument("--project", default=".")
    p.add_argument("--module", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--target", action="append", default=[])
    p.add_argument("--expand-prefix", action="append", default=[])
    p.add_argument("--runner", choices=("lake", "lean"), default="lake")
    p.add_argument("--timeout", type=int, default=600)
    return root


def display_ratio(r):
    if r is None:
        return "unavailable / 无法计算"
    if r["value"] is None:
        return f"2^({r['log2']:.6g})"
    return f"{r['value']:.6g}"


def as_text(report):
    meta = report.get("metadata", {})
    lines = ["MAAM — Mathematical-interest metrics / 数学兴趣指标"]
    if meta:
        lines += [f"Corpus / 语料库: {meta['corpus_id']}",
                  f"Comparison theorems / 对照命题: {meta['comparison_theorems']}",
                  f"Length basis / 长度口径: {meta['length_basis']}"]
    rows = report.get("ranking", [report["assessment"]] if "assessment" in report else [])
    if rows:
        lines += ["", "Name | score / 相对分 | T0 | I0 | I1"]
        for r in rows:
            score = f"{r['score']:.2f}" if r["score"] is not None else "unavailable"
            lines.append(f"{r['name']} | {score} | {display_ratio(r['T0'])} | {display_ratio(r['I0'])} | {r['I1']:.6g}")
            for note in r["notes"]:
                lines.append("  " + note)
    else:
        lines += ["", json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)]
    lines += ["", "Relative heuristic, not a probability or an objective verdict on mathematical value.",
              "这是相对于指定语料库的启发式指标，不是数学价值的客观判决。"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "metrics":
            report = direct_metrics(args.signature_wrapped, args.body_wrapped,
                                    args.signature_unwrapped, args.body_unwrapped)
        elif args.command == "validate":
            corpus = Corpus.load(args.corpus)
            report = {"status": "valid", "nodes": len(corpus.nodes), "sha256": corpus.sha256,
                      "formal_correctness": "not checked; graph/schema validation only"}
        elif args.command in {"efficiency", "reuse"}:
            system = ProofSystem.load(args.system)
            report = system.evaluate(args.name) if args.command == "efficiency" else system.reuse_gain(args.name, args.goal)
        elif args.command == "export-lean":
            from .lean import export
            report = export(args.project, args.module, args.output, targets=args.target,
                            expand_prefixes=args.expand_prefix, runner=args.runner, timeout=args.timeout)
        else:
            calc = Calculator(Corpus.load(args.corpus), alpha=args.alpha, beta=args.beta)
            if args.command == "score":
                report = calc.evaluate(args.name)
            elif args.command == "rank":
                report = calc.rank(args.limit)
            else:
                report = calc.query(args.statement)
        rendered = (as_text(report) if getattr(args, "format", "json") == "text"
                    else json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        output = getattr(args, "output", None)
        if output:
            # Do not accidentally overwrite a corpus, source file, or previous report.
            with Path(output).open("x", encoding="utf-8") as handle:
                handle.write(rendered)
        else:
            print(rendered, end="")
        if report.get("status") in {"insufficient_evidence", "ambiguous_statement"}:
            return 2
        if "assessment" in report and report["assessment"]["kind"] == "conjecture":
            return 2
        return 0
    except (CorpusError, OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
