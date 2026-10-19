from pathlib import Path
import tempfile
import unittest

from maam.evolution import prepare, register, run_record
from maam.corpus import CorpusError
from maam.migration import unseal
from scripts.checkpoint_evolution import checkpoint, recover

ROOT = Path(__file__).resolve().parents[1]


class EvolutionCheckpointTests(unittest.TestCase):
    def test_restore_preserves_session_identity_and_launches(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "run"
            prepare(ROOT / "experiments/hom_kernel_evolution/study.json", root,
                    base / "workers", ROOT / "skills/evaluate-theory-package", "a" * 40)
            register(root, "e01", "actual-context-fixture")
            one = checkpoint(root, base / "checkpoints", "after-registration")
            two = checkpoint(root, base / "checkpoints", "second-checkpoint")
            self.assertNotEqual(one, two)
            target = recover(one, base / "restored")
            self.assertEqual(run_record(root)[0], run_record(target)[0])
            self.assertEqual(unseal(root / "baseline/session.json"),
                             unseal(target / "baseline/session.json"))
            self.assertEqual(unseal(target / "launches/e01.json")["agent_id"], "actual-context-fixture")

    def test_recursive_checkpoint_storage_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(CorpusError, "outside"):
                checkpoint(root, root / "checkpoints", "bad")


if __name__ == "__main__":
    unittest.main()
