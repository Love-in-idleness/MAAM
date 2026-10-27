"""New sandbox controls, plus harmless live Lean/namespace acceptance checks."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from maam import lean_sandbox as sandbox
from maam.migration import verify_attempt


class MethodSandboxTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.sysroot = self.root / "toolchain"
        (self.sysroot / "bin").mkdir(parents=True)
        (self.sysroot / "bin/lean").write_text("fixture")
        self.checker = self.root / "PackageCheck.lean"
        self.checker.write_text("fixture")
        self.bwrap = self.root / "bwrap"
        self.bwrap.touch()
        self.work = self.root / "maam-attempt-fixture"
        self.work.mkdir()
        (self.work / "Proof.lean").write_text("fixture")
        self.scratch = self.root / "scratch"
        self.scratch.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(sandbox, "SYSROOT", self.sysroot).start()
        patch.object(sandbox, "CHECKER", self.checker).start()
        patch.object(sandbox, "BWRAP", str(self.bwrap)).start()
        patch.object(sandbox.tempfile, "gettempdir", return_value=str(self.root)).start()

    @staticmethod
    def options(command, option, length):
        return [command[i + 1:i + length + 1] for i, item in enumerate(command) if item == option]

    def test_attempt_is_readonly_and_only_separate_output_is_writable(self):
        command = sandbox.build_command(
            ["-DmaxHeartbeats=200000", "-o", "Proof.olean", "Proof.lean"],
            self.work, scratch=self.scratch)
        self.assertEqual(self.options(command, "--bind", 2), [[str(self.scratch), "/output"]])
        self.assertIn([str(self.work), str(self.work)], self.options(command, "--ro-bind", 2))
        self.assertIn([str(self.sysroot), "/toolchain"], self.options(command, "--ro-bind", 2))
        self.assertEqual(command[-4:], ["-DmaxHeartbeats=200000", "-o", "/output/result.olean", "Proof.lean"])
        self.assertFalse((self.work / "Proof.olean").exists())
        for option in ("--unshare-all", "--unshare-net", "--clearenv", "--die-with-parent"):
            self.assertIn(option, command)
        self.assertNotIn("--share-net", command)
        self.assertEqual(dict(self.options(command, "--setenv", 2)), {
            "PATH": "/toolchain/bin:/usr/bin", "HOME": "/nonexistent", "TMPDIR": "/tmp",
            "LANG": "C.UTF-8", "LEAN_PATH": str(self.work)})
        self.assertEqual(self.options(command, "--remount-ro", 1), [["/"], ["/dev"], ["/proc"]])

    def test_audit_uses_readonly_trusted_checker_and_separate_output(self):
        (self.work / "audit-input.json").write_text("{}")
        command = sandbox.build_command(["--run", str(self.checker), "audit-input.json", "audit-output.json"],
                                        self.work, scratch=self.scratch)
        self.assertEqual(command[-4:], ["--run", "/checker/PackageCheck.lean", "audit-input.json", "/output/result.json"])
        self.assertIn([str(self.checker), "/checker/PackageCheck.lean"], self.options(command, "--ro-bind", 2))

    def test_queries_do_not_expose_attempt_or_output(self):
        for query in (["--version"], ["--print-prefix"]):
            command = sandbox.build_command(query, self.root / "missing")
            self.assertNotIn("--bind", command)
            self.assertNotIn(str(self.work), command)
            self.assertEqual(command[-len(query):], query)

    def test_rejects_other_commands_and_escaping_paths(self):
        commands = [["--run", "Proof.lean"], ["Proof.lean"],
                    ["-DmaxHeartbeats=200000", "-o", "../Proof.olean", "Proof.lean"],
                    ["-DmaxHeartbeats=200000", "-o", "/tmp/Proof.olean", "Proof.lean"],
                    ["-DmaxHeartbeats=200000", "-o", "Proof.lean", "Proof.lean"],
                    ["-DmaxHeartbeats=200000", "-o", "Other.olean", "Proof.lean"]]
        for command in commands:
            with self.subTest(command=command), self.assertRaises(ValueError):
                sandbox.build_command(command, self.work, scratch=self.scratch)
        for directory in (self.root, self.work / "maam-attempt-nested"):
            directory.mkdir(exist_ok=True)
            with self.subTest(directory=directory), self.assertRaises(ValueError):
                sandbox.build_command(["-DmaxHeartbeats=200000", "-o", "Proof.olean", "Proof.lean"],
                                      directory, scratch=self.scratch)

    def test_rejects_symlink_attempt_and_shared_output_tree(self):
        link = self.root / "maam-attempt-link"
        link.symlink_to(self.work, target_is_directory=True)
        with self.assertRaises(ValueError):
            sandbox.build_command(["-DmaxHeartbeats=200000", "-o", "Proof.olean", "Proof.lean"],
                                  link, scratch=self.scratch)
        for scratch in (self.work, self.root):
            with self.subTest(scratch=scratch), self.assertRaises(ValueError):
                sandbox.build_command(["-DmaxHeartbeats=200000", "-o", "Proof.olean", "Proof.lean"],
                                      self.work, scratch=scratch)

    def test_output_rejects_symlinks_and_hardlinks(self):
        output = self.scratch / "output"
        output.write_text("fixture")
        sandbox._regular_output(output)
        link = self.scratch / "symlink"
        link.symlink_to(output)
        with self.assertRaises(ValueError):
            sandbox._regular_output(link)
        hardlink = self.scratch / "hardlink"
        os.link(output, hardlink)
        with self.assertRaises(ValueError):
            sandbox._regular_output(output)

    def test_missing_bwrap_and_failed_probe_never_yield_host_lean(self):
        self.bwrap.unlink()
        with self.assertRaises(sandbox.SandboxUnavailable):
            sandbox.build_command(["--version"])
        with patch.object(sandbox, "_probe", side_effect=sandbox.SandboxUnavailable("user namespace denied")):
            with self.assertRaisesRegex(sandbox.SandboxUnavailable, "namespace denied"):
                with sandbox.lean_sandbox():
                    self.fail("unavailable sandbox yielded an executable")
        failed = subprocess.CompletedProcess([], 1, "", "bwrap: operation not permitted")
        with patch.object(sandbox.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(sandbox.SandboxUnavailable, "operation not permitted"):
                sandbox.probe()


@unittest.skipUnless(shutil.which("bwrap") and (sandbox.SYSROOT / "bin/lean").exists(),
                     "live acceptance requires bubblewrap and pinned Lean 4.24.0")
class LiveMethodSandboxTests(unittest.TestCase):
    def test_real_lean_sentinels_and_existing_verifier(self):
        try:
            evidence = sandbox.probe()
        except sandbox.SandboxUnavailable as exc:
            self.skipTest(str(exc))
        self.assertEqual(evidence["status"], "verified")
        self.assertIn("host_network_denied", evidence["checks"])
        frozen = {"manifest": {"lean_version": "4.24.0", "budget": {
            "per_attempt_timeout_seconds": 30, "per_command_timeout_seconds": 15,
            "max_heartbeats": 200000}}, "package": {"modules": [], "declarations": []},
            "blobs": {"Base": b"namespace Base\ndef goal : Prop := True\nend Base\n"}}
        request = {"condition": "baseline", "sources": [{"module": "Base"}],
                   "task": {"goal": "Base.goal"}}
        proof = ("import Base\nnamespace Submission\n"
                 "theorem solve : Base.goal := by exact True.intro\nend Submission\n")
        with tempfile.TemporaryDirectory() as folder, sandbox.lean_sandbox(check=False) as wrapper:
            result = verify_attempt(frozen, request, proof, Path(folder), lean=str(wrapper))
        self.assertEqual(result["status"], "verified", result)


if __name__ == "__main__":
    unittest.main()
