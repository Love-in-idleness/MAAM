"""Offline phase, metering and crash controls; formal outcomes here are mocked."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch

from maam import CorpusError, generation, transfer
from maam.migration import canonical, save_new, seal, unseal
from maam.transfer_protocol import load_protocol

ROOT = Path(__file__).resolve().parents[1]


class TransferTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        shutil.copytree(ROOT / "experiments/metered_transfer_v1", self.folder / "inputs")
        self.protocol = self.folder / "inputs/protocol.json"
        self.root = self.folder / "run"
        self.sent, self.counted = [], []
        self.preflight = patch("maam.generation.check_lean").start()
        self.verifier = patch("maam.migration.verify_attempt", side_effect=self.verify).start()
        self.addCleanup(patch.stopall)

    @staticmethod
    def verify(frozen, request, source, artifact, **kwargs):
        if "_reject_" in source:
            return {"status": "rejected", "audit": None, "trace": [],
                    "failure": {"kind": "verification_failed", "stage": "compile", "message": "fixture rejection"}}
        sources = [{"module": "Proof", "source_tokens": 40}]
        if request["condition"] == "treatment":
            sources += [{"module": m, "source_tokens": 80} for m in frozen["package"]["modules"]]
        return {"status": "verified", "trace": [], "audit": {
            "targets": [{"name": "Submission.solve", "expected": request["task"]["goal"],
                         "goal_preserved": True, "proof_expr_nodes": 50,
                         "source": {"body_tokens": 30, "signature_tokens": 4, "declaration_tokens": 35}}],
            "sources": sources}}

    def prepare(self, **budget):
        data = json.loads(self.protocol.read_text())
        data["experiment_budget"].update(budget)
        self.protocol.write_text(json.dumps(data))
        return transfer.prepare(self.protocol, self.root, verify_commit=False)

    @staticmethod
    def wire(value):
        return 200, "synthetic-request", canonical(value)

    def count(self, payload, timeout):
        self.counted.append(copy.deepcopy(payload))
        return self.wire({"input_tokens": 100})

    def response(self, *, proof="by trivial", model="deepseek-flash", inputs=100, outputs=40, usage=True, status="completed"):
        value = {"id": "fixture-response", "model": model, "status": status,
                 "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(
                     {"proof": proof, "bridge": "synthetic proof; mocked verifier"})}]}]}
        if usage:
            value["usage"] = {"input_tokens": inputs, "output_tokens": outputs, "total_tokens": inputs + outputs,
                              "output_tokens_details": {"reasoning_tokens": min(10, outputs)}}
        return self.wire(value)

    def transport(self, payload, timeout):
        self.sent.append(copy.deepcopy(payload))
        return self.response()

    def run_phase(self, phase="development", transport=None, count=None):
        return transfer.run(self.root, phase, transport=transport or self.transport, count_input=count or self.count)

    def test_original_splits_and_legacy_scope_are_preserved(self):
        state = self.prepare()
        self.assertEqual(state["status"], "prepared")
        request = generation.task_request(self.root / "stages/reserved/baseline", "r01")
        self.assertEqual(request["task"]["split"], "reserved")
        self.assertEqual([s["module"] for s in request["sources"]], ["Base", "Tasks.R01"])
        self.assertFalse(state["stages"]["reserved"]["generation"]["scope"]["held_out_evaluation"])
        self.assertFalse(state["held_out_effectiveness_claim"])
        self.assertEqual(state["provider"], "deepseek")

    def test_reserved_gate_prevents_counting_and_generation(self):
        self.prepare()
        with self.assertRaisesRegex(CorpusError, "finish the frozen development"):
            self.run_phase("reserved")
        self.assertEqual(self.counted, [])
        self.assertEqual(self.sent, [])

    def test_synthetic_complete_schedule_is_not_provider_evidence(self):
        self.prepare()
        development = self.run_phase()
        self.assertTrue(development["stages"]["development"]["complete"])
        self.assertEqual(development["ledger"]["generation_calls"], 8)
        self.assertEqual(development["stages"]["reserved"]["generation"]["calls"], 0)
        result = self.run_phase("reserved")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["ledger"]["generation_calls"], 16)
        self.assertTrue(result["matched_allocations_complete"])
        self.assertFalse(result["ledger"]["provider_evidence"])
        self.assertFalse(result["exact_model_revision_verified"])
        self.assertFalse(result["training_eligible"])
        self.run_phase("reserved")
        self.assertEqual(len(self.sent), 16)
        ledger = result["stages"]["reserved"]["comparison"]["common_task_source_ledger"]
        self.assertEqual(ledger["package_tokens_charged_once"], 160)
        self.assertEqual(ledger["task_ids"], ["r01", "r02", "r03", "r04"])

    def test_repairs_are_counted_afresh_with_task_local_feedback(self):
        self.prepare()
        sent = []
        def transport(payload, timeout):
            sent.append(copy.deepcopy(payload))
            return self.response(proof="by _reject_" if len(sent) == 1 else "by trivial")
        result = self.run_phase(transport=transport)
        self.assertEqual(result["ledger"]["generation_calls"], 9)
        for counted, generated in zip(self.counted, sent):
            self.assertEqual(counted, {k: v for k, v in generated.items() if k not in {"store", "max_output_tokens"}})
        history = json.loads(sent[1]["input"])["previous_attempts"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["feedback"]["message"], "fixture rejection")
        for payload in sent[2:]:
            self.assertEqual(json.loads(payload["input"])["previous_attempts"], [])

    def test_global_call_cap_stops_before_another_transport(self):
        self.prepare(max_generation_calls=1, max_total_input_tokens=16384, max_total_output_tokens=2048)
        result = self.run_phase()
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(result["stop"]["reason"], "run_call_input_output_or_cost_limit")
        self.assertFalse(result["matched_allocations_complete"])

    def test_input_output_and_cost_caps_prevent_the_first_generation(self):
        for index, budget in enumerate(({"max_total_input_tokens": 99},
                                        {"max_total_output_tokens": 2047}, {"max_cost_usd": "0.000001"})):
            with self.subTest(budget=budget):
                self.root = self.folder / f"limit-{index}"
                self.sent.clear()
                self.prepare(**budget)
                result = self.run_phase()
                self.assertEqual(result["ledger"]["generation_calls"], 0)
                self.assertEqual(self.sent, [])

    def test_bad_input_allowance_or_count_error_does_not_call_provider(self):
        self.prepare()
        result = self.run_phase(count=lambda *args: self.wire({"input_tokens": True}))
        self.assertEqual(result["ledger"]["generation_calls"], 0)
        self.assertEqual(self.sent, [])
        self.assertEqual(result["stop"]["reason"], "input_count_failed_or_over_limit")

    def test_unknown_usage_retains_maximum_and_prevents_resume(self):
        self.prepare()
        transport = Mock(return_value=self.response(usage=False))
        result = self.run_phase(transport=transport)
        self.assertEqual(transport.call_count, 1)
        self.assertIsNone(result["ledger"]["input_tokens"])
        self.assertIsNone(result["ledger"]["output_tokens"])
        self.assertEqual(result["ledger"]["charged_input_tokens"], 100)
        self.assertEqual(result["ledger"]["charged_output_tokens"], 2048)
        self.run_phase(transport=transport)
        self.assertEqual(transport.call_count, 1)

    def test_http_interruption_retains_reservation_and_blocks_resume(self):
        self.prepare()
        transport = Mock(side_effect=KeyboardInterrupt)
        with self.assertRaises(KeyboardInterrupt):
            self.run_phase(transport=transport)
        result = self.run_phase(transport=transport)
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(result["stop"]["reason"], "unknown_usage_or_interrupted_call")
        self.assertTrue(result["ledger"]["interrupted"])
        self.assertEqual(result["ledger"]["charged_output_tokens"], 2048)

    def test_lean_interruption_preserves_known_usage_without_recalling_provider(self):
        self.prepare()
        self.verifier.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.run_phase()
        state = transfer.report(self.root)
        self.assertTrue(state["ledger"]["usage_complete"])
        self.assertTrue(state["ledger"]["interrupted"])
        self.assertEqual(state["ledger"]["output_tokens"], 40)
        self.run_phase()
        self.assertEqual(len(self.sent), 1)

    def test_interrupted_local_preflight_is_not_retried(self):
        self.prepare()
        counter = Mock(side_effect=KeyboardInterrupt)
        with self.assertRaises(KeyboardInterrupt):
            self.run_phase(count=counter)
        result = self.run_phase(count=counter)
        self.assertEqual(counter.call_count, 1)
        self.assertEqual(result["stop"]["reason"], "interrupted_input_count")
        self.assertEqual(result["ledger"]["generation_calls"], 0)

    def test_model_or_usage_overrun_stops_after_one_call(self):
        for index, kwargs in enumerate(({"model": "unexpected-expensive-model"}, {"inputs": 101}, {"outputs": 2049})):
            with self.subTest(kwargs=kwargs):
                self.root = self.folder / f"provider-{index}"
                self.prepare()
                transport = Mock(return_value=self.response(**kwargs))
                result = self.run_phase(transport=transport)
                self.assertEqual(transport.call_count, 1)
                self.assertEqual(result["stop"]["reason"], "provider_limit_or_model_mismatch")

    def test_count_and_cost_reservation_tampering_are_detected(self):
        for index, kind in enumerate(("raw", "cost")):
            self.root = self.folder / f"tamper-{index}"
            self.prepare()
            self.run_phase()
            if kind == "raw":
                (self.root / "input-counts/0001/response.bin").write_bytes(b'{"input_tokens":1}')
            else:
                path = self.root / "budget-reservations/0001.json"
                value = unseal(path)
                value["cost_allowance_usd"] = "0"
                path.write_bytes(canonical(seal(value)))
            with self.assertRaises(CorpusError):
                transfer.report(self.root)

    def test_replay_checks_original_maximum_reservation_not_only_small_actual_usage(self):
        self.prepare()
        self.run_phase()
        protocol = self.root / "snapshot/protocol.json"
        value = json.loads(protocol.read_bytes())
        value["experiment_budget"]["max_total_output_tokens"] = 1024
        protocol.write_bytes(canonical(value))
        path = self.root / "plan.json"
        plan = unseal(path)
        plan["fingerprints"] = load_protocol(protocol)["fingerprints"]
        path.write_bytes(canonical(seal(plan)))
        with self.assertRaisesRegex(CorpusError, "preflight budget"):
            transfer.report(self.root)

    def test_forged_early_development_completion_is_rejected(self):
        self.prepare()
        stage = self.root / "stages/development"
        state = generation.report(stage)
        save_new(stage / "stop.json", seal({"reason": "schedule_exhausted", "calls": 0, "tasks": state["tasks"]}))
        with self.assertRaisesRegex(CorpusError, "before exhausting"):
            self.run_phase("reserved")

    def test_fixture_preparation_cannot_make_a_paid_call(self):
        self.prepare()
        with patch("maam.transfer.read_private_key") as key, patch("maam.deepseek.response") as network:
            with self.assertRaisesRegex(CorpusError, "fixture preparation"):
                transfer.run(self.root, "development", key_file="never-read")
            key.assert_not_called()
            network.assert_not_called()

    def test_paid_inputs_must_exist_in_the_frozen_commit(self):
        with self.assertRaises(CorpusError):
            transfer.prepare(self.protocol, self.root)
        self.assertFalse(self.root.exists())

    def test_changed_payload_is_blocked_before_transport(self):
        self.prepare()
        original = generation.generate_one
        def attack(stage, record, item, state, transport, lean, kind):
            wrong = copy.deepcopy(transfer.next_payload(stage, record, state)[1])
            wrong["model"] = "unapproved-model"
            with self.assertRaisesRegex(OSError, "uncounted_or_extra_payload_blocked"):
                transport(wrong, 1)
            return original(stage, record, item, state, transport, lean, kind)
        with patch("maam.generation.generate_one", side_effect=attack):
            result = self.run_phase()
        self.assertEqual(len(self.sent), 8)
        self.assertTrue(result["stages"]["development"]["complete"])

    def test_production_route_uses_only_deepseek_and_full_local_allowances(self):
        self.prepare()
        # Simulate committed preparation without calling Git or a real provider.
        path = self.root / "plan.json"
        plan = unseal(path)
        plan["freeze_commit"] = "f" * 40
        path.write_bytes(canonical(seal(plan)))
        key = "sk-synthetic-private-fixture-" + "G" * 32
        with patch("maam.transfer.read_private_key", return_value=key) as reader, \
             patch("maam.deepseek.response", return_value=self.response()) as deepseek_http, \
             patch("maam.generation.openai_response") as openai_http:
            result = transfer.run(self.root, "development", key_file="synthetic-deepseek-path")
        reader.assert_called_once_with("synthetic-deepseek-path")
        openai_http.assert_not_called()
        self.assertEqual(deepseek_http.call_count, 8)
        self.assertTrue(result["ledger"]["provider_evidence"])
        self.assertFalse(result["stages"]["development"]["generation"]["provider_usage_observed"])
        for call in deepseek_http.call_args_list:
            self.assertEqual(call.args[0], key)
            self.assertEqual(call.args[1]["model"], "deepseek-flash")
        for file in self.root.rglob("*"):
            if file.is_file():
                self.assertNotIn(key.encode(), file.read_bytes())
                self.assertNotIn(b"synthetic-deepseek-path", file.read_bytes())


if __name__ == "__main__":
    unittest.main()
