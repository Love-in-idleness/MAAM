"""Conditional coverage on a documented finite implication hypergraph."""

from collections import Counter
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
from urllib.parse import urlsplit

from .corpus import CorpusError
from .proofs import ProofSystem


def _text(obj, key, context):
    value = obj.get(key) if isinstance(obj, dict) else None
    if not isinstance(value, str) or not value.strip() or len(value.splitlines()) != 1:
        raise CorpusError(f"{context}: {key} must be a nonempty single line")
    return value


def _source(obj, context):
    source = _text(obj, "source", context)
    url = urlsplit(source)
    if url.scheme != "https" or not url.hostname or any(c.isspace() or c in '<>' for c in source):
        raise CorpusError(f"{context}: source must be an HTTPS URL")


def _selection(data, key, statements):
    items = data.get(key)
    if not isinstance(items, list) or not items:
        raise CorpusError(f"{key} must be a nonempty array")
    if any(not isinstance(item, str) or item not in statements for item in items):
        raise CorpusError(f"{key} must reference known statement IDs")
    if len(set(items)) != len(items):
        raise CorpusError(f"{key} must contain distinct statements")
    return items


def _read_corpus(raw):
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise CorpusError("expected a conjecture corpus with schema_version: 1")
    corpus_id = _text(data, "corpus_id", "corpus")
    _text(data, "reviewed_on", "corpus")
    statements = data.get("statements")
    if not isinstance(statements, dict) or not statements:
        raise CorpusError("statements must be a nonempty object")
    for name, entry in statements.items():
        if not name.strip():
            raise CorpusError("statement IDs must be nonempty")
        for key in ("label_zh", "label_en", "statement", "family"):
            _text(entry, key, name)
        if entry.get("status") not in ("open", "established"):
            raise CorpusError(f"{name}: status must be open or established")
        _source(entry, name)

    candidates = _selection(data, "candidates", statements)
    targets = _selection(data, "targets", statements)
    if any(statements[name]["status"] != "open" for name in candidates):
        raise CorpusError("all candidates must be open")
    rules = data.get("rules")
    if not isinstance(rules, list):
        raise CorpusError("rules must be an array")
    for rule in rules:
        rule_id = _text(rule, "id", "rule")
        _source(rule, rule_id)
        _text(rule, "locator", rule_id)
        _text(rule, "argument", rule_id)
        if not isinstance(rule.get("premises"), list) or not rule["premises"]:
            raise CorpusError(f"{rule_id}: rules need at least one explicit premise")

    system = ProofSystem({
        "schema_version": 1,
        "system_id": corpus_id,
        # Unit lengths only select a witness path. They are never scored as proof costs.
        "statement_lengths": dict.fromkeys(statements, 1),
        "axioms": [name for name, entry in statements.items() if entry["status"] == "established"],
        "rules": rules,
    })
    return data, system, candidates, targets


def _witness_rules(target, costs, witnesses, rules):
    steps = set()
    pending = [target]
    while pending:
        name = pending.pop()
        if name in steps or witnesses[name]["kind"] != "rule":
            continue
        steps.add(name)
        pending.extend(rules[witnesses[name]["rule"]]["premises"])
    return [witnesses[name]["rule"] for name in sorted(steps, key=lambda name: (costs[name], name))]


def _ranks(counts):
    frequency = Counter(counts.values())
    rank_by_count = {}
    next_rank = 1
    for count in sorted(frequency, reverse=True):
        rank_by_count[count] = next_rank
        next_rank += frequency[count]
    return {name: rank_by_count[count] for name, count in counts.items()}


def rank_conjectures(path):
    raw = Path(path).read_bytes()
    data, system, candidates, targets = _read_corpus(raw)
    statements = data["statements"]
    rules = {rule["id"]: rule for rule in data["rules"]}
    baseline, _ = system.solve()
    open_targets = [target for target in targets if target not in baseline]
    target_families = sorted({statements[target]["family"] for target in open_targets})
    solutions = {name: system.solve(reusable=name) for name in sorted(set(candidates) | set(open_targets))}
    for left, right in combinations(open_targets, 2):
        if right in solutions[left][0] and left in solutions[right][0]:
            if statements[left]["family"] != statements[right]["family"]:
                raise CorpusError(f"equivalent targets must share a family: {left}, {right}")
    ranking = []
    for name in candidates:
        costs, witnesses = solutions[name]
        consequences, equivalent = [], []
        for target in open_targets:
            if target == name or target not in costs:
                continue
            finding = {"id": target, "family": statements[target]["family"],
                       "rule_ids": _witness_rules(target, costs, witnesses, rules)}
            if name in solutions[target][0]:
                reverse_costs, reverse_witnesses = solutions[target]
                finding["reverse_rule_ids"] = _witness_rules(name, reverse_costs, reverse_witnesses, rules)
                equivalent.append(finding)
            else:
                consequences.append(finding)
        families = sorted({finding["family"] for finding in consequences})
        ranking.append({"id": name, "coverage": len(families), "families": families,
                        "new_open_targets": consequences, "recorded_equivalences": equivalent})

    ranks = _ranks({row["id"]: row["coverage"] for row in ranking})
    omitted = {
        family: _ranks({row["id"]: row["coverage"] - int(family in row["families"]) for row in ranking})
        for family in target_families
    }
    for row in ranking:
        name = row["id"]
        row["rank"] = ranks[name]
        observed = [ranks[name], *(ranks_without[name] for ranks_without in omitted.values())]
        row["rank_range_on_single_family_removal"] = [min(observed), max(observed)]

    return {
        "schema_version": 1,
        "status": "evaluated",
        "corpus_id": data["corpus_id"],
        "reviewed_on": data["reviewed_on"],
        "corpus_sha256": sha256(raw).hexdigest(),
        "method": "finite_conditional_coverage_by_open_target_family_v1",
        "evidence": "curated source citations and arguments; finite reachability computed by MAAM",
        "baseline_targets": [target for target in targets if target in baseline],
        "target_families": target_families,
        "ranks_without_family": omitted,
        "ranking": sorted(ranking, key=lambda row: (row["rank"], row["id"])),
        "targets": targets,
        "statements": statements,
        "rules": data["rules"],
    }


def as_markdown(report):
    def cell(value):
        return value.replace("|", r"\|")

    def label(name):
        entry = report["statements"][name]
        if entry["label_zh"] == entry["label_en"]:
            return cell(entry["label_zh"])
        return cell(f"{entry['label_zh']} / {entry['label_en']}")

    lines = [
        "# MAAM 开放猜想榜 / Open conjecture ranking",
        "",
        f"`{report['corpus_id']}` · {report['reviewed_on']} · SHA-256 `{report['corpus_sha256']}`",
        "",
        "分数是单独加入该猜想后可推出的开放目标族数。同分并列。"
        "名次范围包含全样本及逐次去掉一个目标族后的结果。",
        "",
        "The score counts families of open targets reached by assuming that one conjecture. "
        "Equal scores share a rank. The range includes the full panel and each single-family omission.",
        "",
        "| 名次 / Rank | 猜想 / Conjecture | 目标族数 / Families | 名次范围 / Range | 新覆盖 / New targets |",
        "| ---: | --- | ---: | --- | --- |",
    ]
    for row in report["ranking"]:
        low, high = row["rank_range_on_single_family_removal"]
        rank_range = str(low) if low == high else f"{low}–{high}"
        targets = "<br>".join(label(target["id"]) for target in row["new_open_targets"]) or "—"
        lines.append(f"| {row['rank']} | {label(row['id'])} | {row['coverage']} | {rank_range} | {targets} |")

    lines.extend(["", "## 证据索引 / Evidence index", "",
                  "边由文献和书面推理提供，MAAM 计算传递闭包。目标与分组由本语料选定。"
                  "零分表示这份语料没有发现可计分的目标。",
                  "",
                  "Sources and written arguments supply the edges. MAAM computes the closure. "
                  "The corpus fixes the target panel and its families. Zero means this corpus found no scorable target.",
                  "",
                  "### 目标与分组 / Target panel and families", ""])
    for target in report["targets"]:
        entry = report["statements"][target]
        lines.append(f"- {label(target)} · `{entry['family']}` · {entry['status']} · [source](<{entry['source']}>)")
    lines.extend(["", "### 推导规则 / Implication rules", ""])
    for rule in report["rules"]:
        premises = " + ".join(label(premise) for premise in rule["premises"])
        lines.append(f"- `{rule['id']}` · {premises} → {label(rule['conclusion'])}. "
                     f"{rule['argument']} [{rule['locator']}](<{rule['source']}>)")
    lines.extend(["", "### 榜单推导路径 / Witness paths", ""])
    for row in report["ranking"]:
        for target in row["new_open_targets"]:
            path = " → ".join(f"`{rule_id}`" for rule_id in target["rule_ids"])
            lines.append(f"- {label(row['id'])} ⇒ {label(target['id'])} · {path}")
    lines.extend(["", "### 已记录的等价表述 / Recorded equivalent formulations", ""])
    for row in report["ranking"]:
        for target in row["recorded_equivalences"]:
            lines.append(f"- {label(row['id'])} ↔ {label(target['id'])}.")
    lines.append("")
    return "\n".join(lines)
