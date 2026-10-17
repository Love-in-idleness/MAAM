import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]


class CLITests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "maam", *args], cwd=ROOT,
                              capture_output=True, text=True)

    def test_real_command_score(self):
        result = self.run_cli("score", "--corpus", "examples/paper_simple_lemma.json", "--name", "simple_lemma")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["assessment"]["I0"]["value"], 4/3)

    def test_direct_measures(self):
        result = self.run_cli("metrics", "--signature-wrapped", "10", "--body-wrapped", "90",
                              "--signature-unwrapped", "100", "--body-unwrapped", "9000")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["T0"]["value"], 91)

    def test_unrecognised_statement_not_fabricated(self):
        result = self.run_cli("query", "--corpus", "examples/paper_simple_lemma.json",
                              "--statement", "Every even integer greater than 2 is a sum of two primes")
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(json.loads(result.stdout)["score"])

    def test_rank_text(self):
        result = self.run_cli("rank", "--corpus", "examples/paper_simple_lemma.json", "--format", "text")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("simple_lemma", result.stdout)

    def test_invalid_parameters_and_missing_files(self):
        for args in [("validate", "does-not-exist.json"),
                     ("rank", "--corpus", "examples/paper_simple_lemma.json", "--alpha", "nan")]:
            result = self.run_cli(*args)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stderr)["status"], "error")

    def test_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "report.json"
            path.write_text("keep me", encoding="utf-8")
            result = self.run_cli("rank", "--corpus", "examples/paper_simple_lemma.json", "--output", str(path))
            self.assertEqual(result.returncode, 1)
            self.assertEqual(path.read_text(), "keep me")

    def test_missing_lean_fails_cleanly(self):
        from maam.lean import export
        from maam import CorpusError
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp, patch("maam.lean.shutil.which", return_value=None):
            with self.assertRaisesRegex(CorpusError, "not installed"):
                export(temp, "Demo", str(Path(temp)/"out.json"), targets=[], expand_prefixes=[])

    def test_lean_export_corpus_output_is_not_reused_as_report_output(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        from maam.cli import main

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "corpus.json"

            def successful_export(project, module, output, **kwargs):
                Path(output).write_text('{"corpus": "preserve exported data"}', encoding="utf-8")
                return {"status": "exported", "output": output, "nodes": 4}

            stdout = StringIO()
            with patch("maam.lean.export", side_effect=successful_export), redirect_stdout(stdout):
                code = main(["export-lean", "--project", temp, "--module", "Demo", "--output", str(path)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout.getvalue())["status"], "exported")
            self.assertEqual(json.loads(path.read_text()), {"corpus": "preserve exported data"})


if __name__ == "__main__":
    unittest.main()
