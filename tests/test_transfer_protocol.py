"""Protocol validation is offline and does not compile or generate any proofs."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from maam import CorpusError
from maam.theory import digest
from maam.transfer_protocol import (PRICING_SOURCE, SCOPE, STOPPING, cost_for,
                                    load_protocol, schedule)


ROOT = Path(__file__).resolve().parents[1]


class TransferProtocolTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        shutil.copytree(ROOT / "experiments/hom_kernel_migration", self.root / "suite")
        suite = self.root / "suite/suite.json"
        tasks = json.loads(suite.read_text())["tasks"]
        self.path = self.root / "protocol.json"
        self.data = {"schema_version": 1, "study_id": "transfer-fixture",
                     "phase": "pre_registered_transfer_comparison",
                     "suite": {"path": "suite/suite.json", "sha256": digest(suite.read_bytes())},
                     "config": {"model": "deepseek-flash", "sampling": {"reasoning_effort": "low"},
                                "budget": {"max_calls_per_task": 2,
                                           "max_output_tokens_per_call": 2048,
                                           "max_output_tokens_per_task": 4096,
                                           "request_timeout_seconds": 60}},
                     "experiment_budget": {"max_generation_calls": 32,
                                           "max_input_tokens_per_call": 8192,
                                           "max_total_input_tokens": 262144,
                                           "max_total_output_tokens": 65536,
                                           "max_cost_usd": "0.10", "input_usd_per_million": "0.30",
                                           "output_usd_per_million": "1.20", "cost_margin": "1.25",
                                           "pricing_checked_on": "2026-10-20",
                                           "pricing_source": PRICING_SOURCE},
                     "task_order": {split: [t["id"] for t in tasks if t["split"] == split]
                                    for split in ("development", "reserved")},
                     "stopping": copy.deepcopy(STOPPING), "scope": copy.deepcopy(SCOPE)}

    def load(self, data=None):
        self.path.write_text(json.dumps(self.data if data is None else data))
        return load_protocol(self.path)

    def reject(self, data):
        with self.assertRaises(CorpusError):
            self.load(data)

    def test_load_binds_protocol_suite_sources_and_validator(self):
        protocol = self.load()
        self.assertEqual(protocol["manifest"], self.data)
        fingerprints = protocol["fingerprints"]
        self.assertEqual(fingerprints["protocol_sha256"], digest(self.path.read_bytes()))
        self.assertEqual(fingerprints["source_fingerprints"], protocol["frozen"]["fingerprints"])
        self.assertEqual(fingerprints["protocol_validator_sha256"],
                         digest((ROOT / "maam/transfer_protocol.py").read_bytes()))

    def test_both_schedules_alternate_pair_order_without_crossing_splits(self):
        protocol = self.load()
        for split in ("development", "reserved"):
            rows = schedule(protocol, split)
            ids = self.data["task_order"][split]
            self.assertEqual(len(rows), 2 * len(ids))
            self.assertEqual(rows[:4], [{"task_id": ids[0], "condition": "baseline"},
                                       {"task_id": ids[0], "condition": "treatment"},
                                       {"task_id": ids[1], "condition": "treatment"},
                                       {"task_id": ids[1], "condition": "baseline"}])
            self.assertEqual({(r["task_id"], r["condition"]) for r in rows},
                             {(task, condition) for task in ids for condition in ("baseline", "treatment")})
        with self.assertRaises(CorpusError):
            schedule(protocol, "all")

    def test_schema_phase_identity_and_extra_fields(self):
        for key, value in (("schema_version", True), ("schema_version", 2),
                           ("phase", "calibration"), ("study_id", ""), ("study_id", None),
                           ("extra", "unregistered control")):
            with self.subTest(key=key, value=value):
                data = copy.deepcopy(self.data)
                data[key] = value
                self.reject(data)

    def test_missing_fields_are_controlled_errors(self):
        for key in self.data:
            with self.subTest(key=key):
                data = copy.deepcopy(self.data)
                del data[key]
                self.reject(data)

    def test_suite_path_cannot_escape_or_be_absolute(self):
        for path in ("../suite.json", str(self.root / "suite/suite.json")):
            with self.subTest(path=path):
                data = copy.deepcopy(self.data)
                data["suite"]["path"] = path
                self.reject(data)

    def test_suite_descriptor_and_fingerprints_are_checked(self):
        for descriptor in (None, {"path": "suite/suite.json"},
                           {"path": "suite/suite.json", "sha256": "0" * 64},
                           {**self.data["suite"], "extra": True}):
            with self.subTest(descriptor=descriptor):
                data = copy.deepcopy(self.data)
                data["suite"] = descriptor
                self.reject(data)
        (self.root / "suite/Candidate.lean").write_text("-- changed frozen source\n")
        self.reject(self.data)

    def test_model_sampling_and_proof_attempt_capacity_are_pinned(self):
        variants = [("model", "gpt-6.1-sol"), ("sampling", {"reasoning_effort": "high"}),
                    ("sampling", {}), ("sampling", {"reasoning_effort": "low", "temperature": 0})]
        for key, value in variants:
            with self.subTest(key=key, value=value):
                data = copy.deepcopy(self.data)
                data["config"][key] = value
                self.reject(data)
        data = copy.deepcopy(self.data)
        data["config"]["budget"]["max_calls_per_task"] = 4
        self.reject(data)

    def test_order_must_preserve_nonempty_disjoint_splits_and_cover_all_tasks(self):
        variants = []
        for mutate in (lambda order: order["development"].pop(),
                       lambda order: order["development"].append("d01"),
                       lambda order: order["development"].append("r01"),
                       lambda order: order["reserved"].__setitem__(0, "unknown"),
                       lambda order: order.__setitem__("reserved", []),
                       lambda order: order.__setitem__("development", "d01"),
                       lambda order: order["development"].__setitem__(0, []),
                       lambda order: order.__setitem__("extra", [])):
            data = copy.deepcopy(self.data)
            mutate(data["task_order"])
            variants.append(data)
        for index, data in enumerate(variants):
            with self.subTest(index=index):
                self.reject(data)

    def test_integer_limits_reject_boolean_noninteger_nonpositive_values(self):
        fields = ("max_generation_calls", "max_input_tokens_per_call",
                  "max_total_input_tokens", "max_total_output_tokens")
        for field in fields:
            for value in (True, False, 0, -1, 2.0, "32", None):
                with self.subTest(field=field, value=value):
                    data = copy.deepcopy(self.data)
                    data["experiment_budget"][field] = value
                    self.reject(data)

    def test_money_limits_must_be_finite_positive_decimal_strings(self):
        for field in ("max_cost_usd", "input_usd_per_million", "output_usd_per_million", "cost_margin"):
            for value in (True, 1, 0.1, None, "", " 1.0", "0", "-1", "NaN", "Infinity", "sNaN"):
                with self.subTest(field=field, value=value):
                    data = copy.deepcopy(self.data)
                    data["experiment_budget"][field] = value
                    self.reject(data)

    def test_pricing_floor_source_and_calendar_date(self):
        for field, value in (("input_usd_per_million", "0.10"),
                             ("output_usd_per_million", "0.49"), ("cost_margin", "0.99"),
                             ("pricing_source", "https://example.com/prices"),
                             ("pricing_checked_on", "2026-02-30"),
                             ("pricing_checked_on", "20261020"), ("pricing_checked_on", True)):
            with self.subTest(field=field, value=value):
                data = copy.deepcopy(self.data)
                data["experiment_budget"][field] = value
                self.reject(data)

    def test_incomplete_global_budget_is_allowed_but_excess_capacity_is_not(self):
        data = copy.deepcopy(self.data)
        data["experiment_budget"].update(max_generation_calls=1, max_total_input_tokens=1,
                                         max_total_output_tokens=1, max_cost_usd="0.000001")
        self.load(data)
        for field, value in (("max_generation_calls", 81), ("max_total_input_tokens", 262145),
                             ("max_total_output_tokens", 65537)):
            with self.subTest(field=field):
                data = copy.deepcopy(self.data)
                data["experiment_budget"][field] = value
                self.reject(data)

    def test_stopping_and_scope_cannot_silently_promote_evidence(self):
        data = copy.deepcopy(self.data)
        data["stopping"] = list(reversed(STOPPING))
        self.reject(data)
        for field in SCOPE:
            with self.subTest(field=field):
                data = copy.deepcopy(self.data)
                data["scope"][field] = not data["scope"][field]
                self.reject(data)
                data["scope"][field] = int(SCOPE[field])
                self.reject(data)

    def test_cost_uses_decimal_margin_without_double_counting_output(self):
        budget = self.data["experiment_budget"]
        self.assertEqual(cost_for(budget, 262144, 65536), Decimal("0.19660800"))
        self.assertEqual(cost_for(budget, 0, 0), Decimal(0))
        self.assertEqual(cost_for(budget, 2332, 514), Decimal("0.001645500"))
        for tokens in (True, -1, 1.5, "1"):
            with self.subTest(tokens=tokens):
                with self.assertRaises(CorpusError):
                    cost_for(budget, tokens, 0)


if __name__ == "__main__":
    unittest.main()
