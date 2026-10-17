import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

AVAILABLE = all(importlib.util.find_spec(p) for p in ("numpy", "scipy", "matplotlib"))


@unittest.skipUnless(AVAILABLE, "optional scientific dependencies are not installed")
class PaperAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, str(Path(__file__).parents[1]/"scripts"))
        import analyze_mathlib
        cls.analysis = analyze_mathlib

    def test_scc_multiplicity_and_exact_expansion(self):
        import numpy as np
        from scipy.sparse import csr_matrix
        # A -> B twice, B -> A three times; external arcs to p have total 3.
        graph = csr_matrix(np.array([[0,0,0,0],[1,0,2,0],[2,3,0,0],[1,1,0,0]]))
        dag, labels, sizes, cyclic = self.analysis.condensed(graph)
        values, depth, _ = self.analysis.expansion(dag)
        self.assertEqual(int(cyclic.sum()), 1)
        self.assertEqual(len(values), 3)
        self.assertEqual(labels[1], labels[2])
        self.assertEqual(values[labels[1]], 3)
        self.assertEqual(values[labels[3]], 4)
        self.assertEqual(int(depth[labels[3]]), 2)

    def test_sparse_interest_matches_core_calculator(self):
        import numpy as np
        from scipy.sparse import csr_matrix
        from maam import Calculator, Corpus
        nodes = [{"name":"p","kind":"primitive"},
                 {"name":"D","kind":"definition","signature":{"p":1},"body":{"p":3}},
                 {"name":"t","kind":"theorem","signature":{"p":2},"body":{"D":3}}]
        corpus = Corpus({"schema_version":1,"corpus_id":"oracle","nodes":nodes})
        core = Calculator(corpus)
        names = list(corpus.nodes)
        matrix = np.array([[corpus.edges[u].get(v,0) for v in names] for u in names])
        dag, labels, sizes, cyclic = self.analysis.condensed(csr_matrix(matrix))
        values, _, tainted = self.analysis.expansion(dag)
        lengths = [corpus.lengths(corpus.nodes[n]) for n in names]
        ws = np.bincount(labels, weights=[v[0] for v in lengths])
        wb = np.bincount(labels, weights=[v[1] for v in lengths])
        theorem = np.zeros(len(values),dtype=bool)
        theorem[labels[names.index("t")]] = True
        pi, score, info = self.analysis.interest(dag,values,ws,wb,tainted,theorem)
        for k,n in enumerate(names):
            self.assertAlmostEqual(pi[labels[k]], core.raw[n]["I1"], places=11)
        self.assertLess(info["l1_residual"],1e-12)

    def test_actual_index_roundtrip_and_plot_generation(self):
        from maam.index import score_index
        rows=[{"record":"metadata","revision":"synthetic-scc-test"},
              {"record":"node","name":"p","kind":"primitive","signature":{},"body":None},
              {"record":"node","name":"A","kind":"definition","signature":{"p":1},"body":{"B":2},"source":{"status":"named_source","tokens":10}},
              {"record":"node","name":"B","kind":"definition","signature":{"p":2},"body":{"A":3},"source":{"status":"named_source","tokens":12}},
              {"record":"node","name":"T","kind":"theorem","signature":{"p":1},"body":{"A":1},"source":{"status":"named_source","tokens":20}}]
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); raw=root/"raw.jsonl"
            raw.write_text("\n".join(json.dumps(r) for r in rows)+"\n")
            config=Path(__file__).parents[1]/"scripts/paper_config.json"
            report=self.analysis.analyse(raw,root/"report",root/"metrics.sqlite",config)
            self.assertEqual(report["vertices_before_scc"],4)
            self.assertEqual(report["vertices_after_scc"],3)
            self.assertEqual(report["maximum_depth"],2)
            self.assertAlmostEqual(report["maximum_unwrapped_log10"],math.log10(4))
            result=score_index(str(root/"metrics.sqlite"),"T")
            self.assertEqual(result["assessment"]["unwrapped_exact"],"4")
            self.assertEqual(result["assessment"]["score"],50)
            self.assertEqual(len(list((root/"report").glob("*.png"))),4)


if __name__ == "__main__":
    unittest.main()
