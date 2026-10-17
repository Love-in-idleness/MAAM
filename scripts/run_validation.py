#!/usr/bin/env python3
"""Run local unit tests and save their actual outcome for review."""

import json
from pathlib import Path
import platform
import shutil
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
suite = unittest.defaultTestLoader.discover(str(ROOT/"tests"))
result = unittest.TextTestRunner(verbosity=2).run(suite)
summary = {"python_version": platform.python_version(), "tests_run": result.testsRun,
           "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
           "passed": result.wasSuccessful(), "lean_toolchain_available": shutil.which("lean") is not None,
           "remote_ci_executed": False,
           "scope": "local implementation checks, including independent linear-system and hypergraph-relaxation oracles; no human-interest validation"}
(ROOT/"results/validation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
raise SystemExit(0 if result.wasSuccessful() else 1)
