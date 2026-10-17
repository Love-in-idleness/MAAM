"""Strict, closed reference corpora. Unknown dependencies are never invented."""

from collections import Counter, deque
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


class CorpusError(ValueError):
    pass


def natural(value, context: str, *, positive=False) -> int:
    if type(value) is not int or value < (1 if positive else 0):
        raise CorpusError(f"{context} must be a {'positive' if positive else 'non-negative'} integer")
    return value


def references(obj, context: str) -> dict[str, int]:
    if not isinstance(obj, dict):
        raise CorpusError(f"{context} must be an object of declaration: multiplicity")
    for key, value in obj.items():
        if not isinstance(key, str) or not key:
            raise CorpusError(f"{context}: dependency names must be non-empty strings")
        natural(value, f"{context}.{key}", positive=True)
    return dict(obj)


@dataclass(frozen=True)
class Node:
    name: str
    kind: str
    signature: dict[str, int]
    body: dict[str, int] | None
    statement: str | None
    signature_tokens: int | None
    body_tokens: int | None
    domain: str | None
    admitted: bool

    @property
    def edges(self) -> dict[str, int]:
        counts = Counter(self.signature)
        counts.update(self.body or {})
        return dict(counts)


class Corpus:
    def __init__(self, data: dict):
        if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
            raise CorpusError("expected a corpus object with schema_version: 1")
        self.corpus_id = data.get("corpus_id")
        if not isinstance(self.corpus_id, str) or not self.corpus_id.strip():
            raise CorpusError("corpus_id is required")
        self.length_basis = data.get("length_basis", "references")
        if self.length_basis not in {"references", "source_tokens"}:
            raise CorpusError("length_basis must be references or source_tokens")
        self.provenance = data.get("provenance", {})
        if not isinstance(self.provenance, dict):
            raise CorpusError("provenance must be an object")
        raw = data.get("nodes")
        if not isinstance(raw, list) or not raw:
            raise CorpusError("nodes must be a non-empty array")
        self.nodes: dict[str, Node] = {}
        for row in raw:
            if not isinstance(row, dict):
                raise CorpusError("each node must be an object")
            name = row.get("name")
            if not isinstance(name, str) or not name:
                raise CorpusError("each node requires a non-empty name")
            if name in self.nodes:
                raise CorpusError(f"duplicate declaration: {name}")
            kind = row.get("kind")
            if kind not in {"primitive", "axiom", "definition", "theorem", "conjecture"}:
                raise CorpusError(f"{name}: invalid kind")
            sig = references(row.get("signature", {}), f"{name}.signature")
            body = row.get("body")
            if body is not None:
                body = references(body, f"{name}.body")
            if kind == "theorem" and body is None:
                raise CorpusError(f"{name}: theorem needs a body; use kind=conjecture for an unproved statement")
            if kind in {"primitive", "axiom", "conjecture"} and body is not None:
                raise CorpusError(f"{name}: {kind} cannot have a body")
            if kind == "primitive" and sig:
                raise CorpusError(f"{name}: a primitive boundary cannot have outgoing references")
            st, bt = row.get("signature_tokens"), row.get("body_tokens")
            if st is not None:
                natural(st, f"{name}.signature_tokens", positive=True)
            if bt is not None:
                natural(bt, f"{name}.body_tokens")
            if self.length_basis == "source_tokens" and kind != "primitive":
                if st is None or (body is not None and bt is None):
                    raise CorpusError(f"{name}: source_tokens needs separate signature_tokens and body_tokens")
                if body is None and bt not in {None, 0}:
                    raise CorpusError(f"{name}: body_tokens given without a body")
            for field in ("statement", "domain"):
                if row.get(field) is not None and not isinstance(row[field], str):
                    raise CorpusError(f"{name}.{field} must be a string")
            if type(row.get("admitted", False)) is not bool:
                raise CorpusError(f"{name}.admitted must be boolean")
            self.nodes[name] = Node(name, kind, sig, body, row.get("statement"), st, bt,
                                    row.get("domain"), row.get("admitted", False))
        # Sorting makes every report and power iteration independent of input row order.
        self.nodes = dict(sorted(self.nodes.items()))
        self.edges = {k: n.edges for k, n in self.nodes.items()}
        self.users = {k: {} for k in self.nodes}
        for source, edges in self.edges.items():
            for dep, count in edges.items():
                if dep not in self.nodes:
                    raise CorpusError(f"{source}: unknown dependency {dep}; export its closure or declare an explicit primitive")
                if self.nodes[dep].kind == "conjecture":
                    raise CorpusError(f"{source}: cannot use unproved conjecture {dep} as a proved dependency; declare assumptions as axioms")
                self.users[dep][source] = count
        self.order = self._topological_order()
        canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        self.sha256 = hashlib.sha256(canonical.encode()).hexdigest()

    @classmethod
    def load(cls, path: str | Path):
        with open(path, encoding="utf-8") as handle:
            return cls(json.load(handle))

    def _topological_order(self) -> list[str]:
        pending = {k: len(e) for k, e in self.edges.items()}
        queue = deque(k for k in self.nodes if pending[k] == 0)
        order = []
        while queue:
            name = queue.popleft()
            order.append(name)
            for user in sorted(self.users[name]):
                pending[user] -= 1
                if pending[user] == 0:
                    queue.append(user)
        if len(order) != len(self.nodes):
            blocked = sorted(k for k, v in pending.items() if v)
            raise CorpusError("cyclic reference graph (or dependent of a cycle): " + ", ".join(blocked[:12])
                              + "; recursive expansion is not finite; specify primitive boundaries explicitly")
        return order

    def lengths(self, node: Node) -> tuple[int, int | None]:
        if node.kind == "primitive":
            return 1, 0
        if self.length_basis == "source_tokens":
            return node.signature_tokens, (node.body_tokens or 0) if node.kind != "conjecture" else None
        return sum(node.signature.values()), (sum((node.body or {}).values()) if node.kind != "conjecture" else None)
