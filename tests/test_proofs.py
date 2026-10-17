import unittest

from maam import CorpusError, ProofSystem


def fixture():
    return {"schema_version": 1, "system_id": "cost-example",
            "statement_lengths": {"A": 2, "B": 3, "C": 4, "D": 5, "U": 6},
            "axioms": ["A"], "rules": [
                {"id": "A-B", "conclusion": "B", "premises": ["A"]},
                {"id": "B-C", "conclusion": "C", "premises": ["B", "B"]},
                {"id": "A-C", "conclusion": "C", "premises": ["A"]},
                {"id": "BC-D", "conclusion": "D", "premises": ["B", "C"]},
                {"id": "cycle", "conclusion": "U", "premises": ["U"]},
            ]}


class ProofTests(unittest.TestCase):
    def test_alternatives_choose_minimum(self):
        system = ProofSystem(fixture())
        costs, _ = system.solve()
        self.assertEqual(costs, {"A": 2, "B": 5, "C": 6, "D": 16})
        self.assertEqual(system.evaluate("D")["E_finite"]["value"], 16/5)

    def test_multiplicity_is_not_set_semantics(self):
        data = fixture()
        data["rules"] = data["rules"][:2]
        costs, _ = ProofSystem(data).solve()
        self.assertEqual(costs["C"], 4 + 2*5)

    def test_unreachable_cycle_does_not_prove_itself(self):
        system = ProofSystem(fixture())
        self.assertEqual(system.evaluate("U")["status"], "not_derivable_in_supplied_system")
        self.assertIsNone(system.evaluate("U")["E_finite"])

    def test_rule_with_no_premises(self):
        data = fixture()
        data["rules"].append({"id": "U-intro", "conclusion": "U", "premises": []})
        self.assertEqual(ProofSystem(data).solve()[0]["U"], 6)

    def test_reuse_cost_is_amortised(self):
        data = {"schema_version": 1, "system_id": "reuse", "statement_lengths": {
            "A": 1, "L": 2, "G1": 3, "G2": 3}, "axioms": ["A"], "rules": [
                {"id": "build-L", "conclusion": "L", "premises": ["A"]*10},
                {"id": "G1", "conclusion": "G1", "premises": ["L"]},
                {"id": "G2", "conclusion": "G2", "premises": ["L"]}]}
        result = ProofSystem(data).reuse_gain("L", ["G1", "G2"])
        self.assertEqual(result["gross_savings"], 20)
        self.assertEqual(result["construction_cost"], 12)
        self.assertEqual(result["net_savings"], 8)
        data["rules"] = data["rules"][1:]
        self.assertEqual(ProofSystem(data).reuse_gain("L", ["G1"])["status"], "theorem_unproved")

    def test_unknown_rule_nodes_and_lengths(self):
        data = fixture()
        data["rules"][0]["premises"] = ["unknown"]
        with self.assertRaises(CorpusError):
            ProofSystem(data)
        data = fixture()
        data["statement_lengths"]["A"] = 0
        with self.assertRaises(CorpusError):
            ProofSystem(data)

    def test_proof_solver_matches_bellman_oracle(self):
        import random
        rng = random.Random(42)
        for trial in range(25):
            names = [f"s{k}" for k in range(12)]
            lengths = {n: rng.randint(1, 10) for n in names}
            rules = [{"id": f"r{k}", "conclusion": rng.choice(names),
                      "premises": [rng.choice(names) for _ in range(rng.randint(0, 3))]}
                     for k in range(30)]
            data = {"schema_version": 1, "system_id": str(trial), "statement_lengths": lengths,
                    "axioms": names[:2], "rules": rules}
            expected = {n: lengths[n] for n in names[:2]}
            changed = True
            while changed:
                changed = False
                for r in rules:
                    if all(n in expected for n in r["premises"]):
                        cost = lengths[r["conclusion"]] + sum(expected[n] for n in r["premises"])
                        if r["conclusion"] not in expected or cost < expected[r["conclusion"]]:
                            expected[r["conclusion"]] = cost
                            changed = True
            self.assertEqual(ProofSystem(data).solve()[0], expected)


if __name__ == "__main__":
    unittest.main()
