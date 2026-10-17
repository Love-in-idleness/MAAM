import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from maam import CorpusError
from maam.lean import export


class LeanWrapperTests(unittest.TestCase):
    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/"out.json"
            out.write_text("keep me")
            with patch("maam.lean.shutil.which", return_value="lean"), self.assertRaisesRegex(CorpusError, "already exists"):
                export(temp, "Demo", str(out), targets=[], expand_prefixes=[], runner="lean")
            self.assertEqual(out.read_text(), "keep me")

    def test_failed_export_is_not_success(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.CompletedProcess([], 1, "compile failure", "error")
            with patch("maam.lean.shutil.which", return_value="lean"), patch("maam.lean.subprocess.run", return_value=result):
                with self.assertRaisesRegex(CorpusError, "Lean export failed"):
                    export(temp, "Demo", str(Path(temp)/"out.json"), targets=[], expand_prefixes=[], runner="lean")

    def test_module_names_are_validated(self):
        with tempfile.TemporaryDirectory() as temp, patch("maam.lean.shutil.which", return_value="lean"):
            with self.assertRaisesRegex(CorpusError, "module must"):
                export(temp, "Demo;bad", str(Path(temp)/"out.json"), targets=[], expand_prefixes=[], runner="lean")


if __name__ == "__main__":
    unittest.main()
