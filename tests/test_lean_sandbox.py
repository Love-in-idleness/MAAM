"""Sandbox command construction without running Lean, namespaces or a provider."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lean_sandbox.py"
SPEC = importlib.util.spec_from_file_location("maam_lean_sandbox", SCRIPT)
sandbox = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sandbox)


class LeanSandboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.sysroot = self.root / "toolchain"
        (self.sysroot / "bin").mkdir(parents=True)
        (self.sysroot / "bin/lean").write_text("fixture")
        self.checker = self.root / "PackageCheck.lean"
        self.checker.write_text("fixture")
        self.attempt = self.root / "maam-attempt-fixture"
        self.attempt.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(sandbox, "SYSROOT", self.sysroot).start()
        patch.object(sandbox, "CHECKER", self.checker).start()
        patch.object(sandbox.tempfile, "gettempdir", return_value=str(self.root)).start()

    @staticmethod
    def options(command, option, length):
        return [command[i + 1:i + 1 + length] for i, part in enumerate(command) if part == option]

    def test_compile_mounts_only_attempt_writable_and_required_files_readonly(self):
        arguments = ["-DmaxHeartbeats=200000", "-o", "Proof.olean", "Proof.lean"]
        command = sandbox.build_command(arguments, self.attempt)
        self.assertEqual(self.options(command, "--bind", 2), [[str(self.attempt), str(self.attempt)]])
        self.assertEqual(self.options(command, "--ro-bind", 2), [
            ["/usr", "/usr"], [str(self.sysroot), str(self.sysroot)],
            [str(self.checker), str(self.checker)]])
        self.assertEqual(self.options(command, "--chdir", 1), [[str(self.attempt)]])
        self.assertEqual(command[-len(arguments):], arguments)
        self.assertEqual(command[command.index("--") + 1], str(self.sysroot / "bin/lean"))

    def test_queries_never_mount_the_callers_directory(self):
        for arguments in (["--version"], ["--print-prefix"]):
            with self.subTest(arguments=arguments):
                command = sandbox.build_command(arguments, self.root / "nonexistent")
                self.assertNotIn("--bind", command)
                self.assertNotIn("LEAN_PATH", command)
                self.assertEqual(self.options(command, "--chdir", 1), [["/"]])

    def test_network_process_and_environment_isolation_are_required(self):
        command = sandbox.build_command(["--version"])
        for option in ("--unshare-all", "--new-session", "--die-with-parent", "--clearenv"):
            self.assertIn(option, command)
        self.assertNotIn("--share-net", command)
        self.assertNotIn("--unshare-user-try", command)
        self.assertNotIn("--not-a-security-boundary", command)
        environment = dict(self.options(command, "--setenv", 2))
        self.assertEqual(environment, {"PATH": str(self.sysroot / "bin") + ":/usr/bin",
                                       "HOME": "/tmp", "TMPDIR": "/tmp", "LANG": "C.UTF-8"})
        self.assertEqual(self.options(command, "--proc", 1), [["/proc"]])
        self.assertEqual(self.options(command, "--tmpfs", 1), [["/tmp"]])

    def test_audit_receives_unchanged_arguments(self):
        arguments = ["--run", str(self.checker), "audit-input.json", "audit-output.json"]
        command = sandbox.build_command(arguments, self.attempt)
        self.assertEqual(command[-len(arguments):], arguments)
        self.assertEqual(dict(self.options(command, "--setenv", 2))["LEAN_PATH"], str(self.attempt))

    def test_repository_nested_and_unexpected_directories_are_rejected(self):
        nested = self.attempt / "maam-attempt-nested"
        nested.mkdir()
        ordinary = self.root / "other-directory"
        ordinary.mkdir()
        for directory in (self.root, nested, ordinary, SCRIPT.parent):
            with self.subTest(directory=directory):
                with self.assertRaises(ValueError):
                    sandbox.build_command(["Proof.lean"], directory)

    def test_symlink_and_wrong_owner_are_rejected(self):
        link = self.root / "maam-attempt-link"
        link.symlink_to(self.attempt, target_is_directory=True)
        with self.assertRaises(ValueError):
            sandbox.build_command(["Proof.lean"], link)
        with patch.object(sandbox.os, "getuid", return_value=self.attempt.stat().st_uid + 1):
            with self.assertRaises(ValueError):
                sandbox.build_command(["Proof.lean"], self.attempt)

    def test_missing_toolchain_or_checker_does_not_fall_back_to_host_lean(self):
        for target in ("SYSROOT", "CHECKER"):
            with self.subTest(target=target), patch.object(sandbox, target, self.root / "missing"):
                with self.assertRaises(OSError):
                    sandbox.build_command(["--version"])

    def test_arguments_remain_literal_and_extra_query_arguments_need_valid_cwd(self):
        arguments = ["--run", "a file; $(unwanted).lean"]
        command = sandbox.build_command(arguments, self.attempt)
        self.assertEqual(command[-2:], arguments)
        with self.assertRaises(ValueError):
            sandbox.build_command(["--version", "Proof.lean"], self.root)


if __name__ == "__main__":
    unittest.main()
