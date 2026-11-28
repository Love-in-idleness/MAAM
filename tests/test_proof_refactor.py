import unittest

from maam.proof_portfolio import SHARED, project
from maam.proof_refactor import apply_shared, call_arguments, min_route, splice
from maam.theory import CorpusError


class ProofRefactoringTests(unittest.TestCase):
    def test_route_id_does_not_change_compression(self):
        source = "import Base\ntheorem example : True := trivial\n"
        route = {"status": "verified", "sources": {"Proofs.example": source.encode()},
                 "proof_modules": {"example": "Proofs.example"}, "tokens": {"Proofs.example": 10},
                 "nodes": {"Proofs.example": 2}, "uses_shared": [], "uses_candidate": [],
                 "candidate_modules": []}
        for metric in ("zlib_9_bytes", "bzip2_9_bytes"):
            first = min_route({"route-1": route}, ["example"], metric)
            second = min_route({"route-489094": route}, ["example"], metric)
            self.assertEqual(first["cost"], second["cost"])

    def test_subset_charges_only_required_new_modules_once(self):
        modules = {name: (name + "\n").encode() for name in ("Proof.A", "Proof.B", "Proof.C", SHARED, "Candidate")}
        route = {"status": "verified", "sources": modules, "tokens": dict.fromkeys(modules, 1),
                 "nodes": dict.fromkeys(modules, 1), "proof_modules": {"a": "Proof.A", "b": "Proof.B", "c": "Proof.C"},
                 "uses_shared": ["a", "b"], "uses_candidate": ["b"], "candidate_modules": ["Candidate"]}
        self.assertEqual(project(route, ["a", "b"])["source_tokens"], 4)
        self.assertEqual(project(route, ["a", "b"], "installed")["source_tokens"], 3)
        self.assertEqual(project(route, ["c"])["charged_modules"], ["Proof.C"])
        self.assertEqual(project(route, ["c"], "mandatory")["charged_modules"], ["Candidate", "Proof.C"])
        with self.assertRaises(CorpusError):
            project({**route, "status": "rejected"}, ["c"])

    def test_splices_utf8_spans_and_rejects_overlaps(self):
        term = "by\n  -- λ\n  have h := True.intro\n  exact h"
        source = term.encode()
        site = {"start": source.index(b"have "), "stop": source.index(b"\n  exact")}
        self.assertEqual(splice(term, [(site, "have h := trivial")]),
                         "by\n  -- λ\n  have h := trivial\n  exact h")
        with self.assertRaises(CorpusError):
            splice(term, [(site, ""), (site, "")])

    def test_arguments_match_types_and_reject_ambiguous_premises(self):
        anchor = {"binders": [{"index": 0, "key": "T"}, {"index": None, "key": "P"}]}
        target = {"support": ["Object"], "context": [{"name": "hp", "key": "P"}]}
        self.assertEqual(call_arguments(anchor, target), ["Object", "hp"])
        target["context"].append({"name": "hq", "key": "P"})
        self.assertIsNone(call_arguments(anchor, target))

    def test_only_removed_users_allow_pruning_and_only_callers_import(self):
        proof = "by\n  have support := True.intro\n  have h : True := support\n  exact h"
        helper = {"name": "support", "start": 5, "stop": proof.index("\n  have h"),
                  "in_body": False, "users": ["h"]}
        used = {"name": "h", "start": proof.index("have h"), "stop": proof.index("\n  exact"),
                "in_body": True, "users": []}
        proposal = {"seed": ("one", used), "body": " : True := True.intro",
                    "calls": [("one", used, []), ("two", used, [])]}
        terms = {"one": proof, "two": proof, "three": "True.intro"}
        catalog = {"one": [helper, used], "two": [{**helper, "users": ["h", "stillNeeded"]}, used]}
        changed, shared, imports, evidence = apply_shared(terms, catalog, [proposal], ["Base"])
        self.assertEqual(imports, ("one", "two"))
        self.assertIn("theorem shared_1 : True", shared)
        self.assertNotIn("have support", changed["one"])
        self.assertIn("have support", changed["two"])
        self.assertEqual(changed["three"], terms["three"])
        self.assertEqual(evidence["removed_bindings"], [{"task": "one", "local_name": "support", "former_users": ["h"]}])
