"""Fail-closed Linux isolation for the existing migration verifier.

This protects host files and networking. It does not make Lean or its in-process
declaration auditor safe against arbitrary runtime compromise.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import subprocess
import sys
import tempfile


SYSROOT = (Path(pwd.getpwuid(os.getuid()).pw_dir) / ".elan/toolchains"
           / "leanprover--lean4---v4.24.0")
CHECKER = Path(__file__).with_name("PackageCheck.lean")
BWRAP = "/usr/bin/bwrap"


class SandboxUnavailable(RuntimeError):
    """Isolation could not be established; never fall back to host Lean."""


def _attempt(cwd):
    path = Path(cwd).absolute()
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or path != path.resolve(strict=True)
            or path.parent != Path(tempfile.gettempdir()).resolve()
            or not path.name.startswith("maam-attempt-")):
        raise ValueError("expected an owned, direct maam-attempt-* temporary directory")
    return path


def _local_file(work, name, suffix):
    relative = Path(name)
    if (relative.is_absolute() or ".." in relative.parts
            or relative.suffix != suffix):
        raise ValueError("unexpected verifier file path")
    path = work / relative
    if path.parent.resolve(strict=True) != path.parent:
        raise ValueError("verifier file parents must not be symlinks")
    return path


def _regular_output(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
        raise ValueError("sandbox output must be an owned regular file without hard links")


def build_command(arguments, cwd=None, *, scratch=None):
    """Expose the toolchain, checker, immutable inputs, and a scratch output directory."""
    toolchain = SYSROOT.resolve(strict=True)
    checker = CHECKER.resolve(strict=True)
    if not (toolchain / "bin/lean").is_file() or not checker.is_file():
        raise ValueError("pinned Lean and checker must exist")
    if not Path(BWRAP).is_file():
        raise SandboxUnavailable("bubblewrap is not installed: " + BWRAP)
    arguments = list(arguments)
    work = output = None
    if arguments not in (["--version"], ["--print-prefix"]):
        work = _attempt(Path.cwd() if cwd is None else cwd)
        if (len(arguments) == 4 and re.fullmatch(r"-DmaxHeartbeats=[1-9][0-9]*", arguments[0])
                and arguments[1] == "-o"):
            output = _local_file(work, arguments[2], ".olean")
            source = _local_file(work, arguments[3], ".lean")
            if source != output.with_suffix(".lean") or not source.is_file():
                raise ValueError("compile output must match its existing Lean source")
        elif arguments == ["--run", str(CHECKER.resolve()), "audit-input.json", "audit-output.json"]:
            if not (work / "audit-input.json").is_file():
                raise ValueError("audit input is missing")
            output = work / "audit-output.json"
            arguments[1] = "/checker/PackageCheck.lean"
        else:
            raise ValueError("only migration verifier compile, audit, and query commands are allowed")
        if scratch is None:
            raise ValueError("compilation requires a separate scratch output directory")
        scratch = Path(scratch).resolve(strict=True)
        if scratch == work or work in scratch.parents or scratch in work.parents:
            raise ValueError("scratch output and frozen input directories must be separate")
        if len(arguments) == 4 and arguments[1] == "-o":
            arguments[2] = "/output/result.olean"
        else:
            arguments[3] = "/output/result.json"
    command = [BWRAP, "--unshare-all", "--unshare-net", "--die-with-parent", "--new-session",
               "--clearenv", "--cap-drop", "ALL", "--ro-bind", "/usr", "/usr",
               "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib",
               "--symlink", "usr/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev",
               "--size", "67108864", "--tmpfs", "/tmp", "--ro-bind", str(toolchain), "/toolchain",
               "--ro-bind", str(checker), "/checker/PackageCheck.lean",
               "--setenv", "PATH", "/toolchain/bin:/usr/bin", "--setenv", "HOME", "/nonexistent",
               "--setenv", "TMPDIR", "/tmp", "--setenv", "LANG", "C.UTF-8"]
    if work is not None:
        command += ["--ro-bind", str(work), str(work), "--bind", str(scratch), "/output",
                    "--setenv", "LEAN_PATH", str(work), "--chdir", str(work)]
    else:
        command += ["--chdir", "/"]
    return command + ["--remount-ro", "/", "--remount-ro", "/dev", "--remount-ro", "/proc",
                      "--", "/toolchain/bin/lean", *arguments]


@contextmanager
def lean_sandbox(*, check=True):
    """Yield a temporary executable accepted by migration.verify_attempt's `lean`."""
    with tempfile.TemporaryDirectory(prefix="maam-lean-wrapper-") as folder:
        wrapper = Path(folder) / "lean"
        wrapper.write_text("#!" + sys.executable + "\nimport runpy\nraise SystemExit(runpy.run_path("
                           + repr(str(Path(__file__).resolve())) + ")[\"main\"](scratch_root="
                           + repr(folder) + "))\n")
        wrapper.chmod(0o700)
        if check:
            _probe(wrapper)
        yield wrapper


def _run(wrapper, arguments, *, cwd=None, env=None):
    try:
        result = subprocess.run([str(wrapper), *arguments], cwd=cwd, env=env, capture_output=True,
                                text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SandboxUnavailable("Lean sandbox capability check failed: " + str(exc)) from exc
    if result.returncode:
        raise SandboxUnavailable("Lean sandbox capability check failed: "
                                 + (result.stderr or result.stdout)[-4000:])
    return result.stdout


def _probe(wrapper):
    version = _run(wrapper, ["--version"])
    if re.search(r"version 4\.24\.0(?:\D|$)", version) is None:
        raise SandboxUnavailable("sandbox did not run pinned Lean 4.24.0: " + version)
    with (tempfile.TemporaryDirectory(prefix="maam-attempt-") as folder,
          tempfile.TemporaryDirectory(prefix="maam-private-", dir=Path.home()) as private,
          socket.socket() as listener):
        work = Path(folder)
        sentinel = Path(private) / "sentinel"
        sentinel.write_text("harmless private-file sentinel")
        (work / "frozen.lean").write_text("immutable source sentinel")
        (work / "frozen.olean").write_text("immutable compiled sentinel")
        (work / "audit-input.json").write_text("{}")
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        # Run the attack from a Lean metaprogram, not merely from the wrapper.
        code = "\n".join([
            "import os, pathlib, socket",
            "assert os.environ.get('MAAM_SANDBOX_PRIVATE') is None",
            "assert not pathlib.Path(" + repr(str(sentinel)) + ").exists()",
            "assert not pathlib.Path(" + repr(str(Path.home())) + ").exists()",
            "for name in ['Probe.lean', 'frozen.lean', 'frozen.olean', 'audit-input.json', '/checker/PackageCheck.lean', '/toolchain/bin/lean']:",
            "    try:",
            "        stream = open(name, 'r+b')",
            "    except OSError:",
            "        pass",
            "    else:",
            "        stream.close()",
            "        raise AssertionError('writable frozen input: ' + name)",
            "pathlib.Path('/output/scratch').write_text('writable output sentinel')",
            "pathlib.Path('/tmp/scratch').write_text('ephemeral scratch')",
            "client = socket.socket(); client.settimeout(1)",
            "assert client.connect_ex(('127.0.0.1', " + str(port) + ")) != 0",
            "client.close()",
            "print('maam-sandbox-acceptance-ok')",
        ])
        source = ('import Init\n#eval do\n  let result ← IO.Process.output '
                  '{cmd := "/usr/bin/python3", args := #["-c", ' + json.dumps(code) + ']}\n'
                  '  if result.exitCode != 0 then throw <| IO.userError result.stderr\n'
                  '  IO.print result.stdout\n')
        (work / "Probe.lean").write_text(source)
        result = _run(wrapper, ["-DmaxHeartbeats=200000", "-o", "Probe.olean", "Probe.lean"],
                      cwd=work, env={**os.environ, "MAAM_SANDBOX_PRIVATE": "harmless environment sentinel"})
        if "maam-sandbox-acceptance-ok" not in result:
            raise SandboxUnavailable("Lean sandbox sentinel checks did not complete")
        if (sentinel.read_text() != "harmless private-file sentinel"
                or (work / "frozen.lean").read_text() != "immutable source sentinel"
                or (work / "frozen.olean").read_text() != "immutable compiled sentinel"):
            raise SandboxUnavailable("sandbox changed protected sentinel files")
    return {"status": "verified", "lean_version": version.strip(),
            "checks": ["private_file_denied", "home_denied", "private_environment_removed",
                       "frozen_source_readonly", "prior_olean_readonly", "audit_input_readonly",
                       "checker_readonly", "toolchain_readonly", "output_writable", "host_network_denied"]}


def probe():
    """Check real host capability and harmless sentinels; raise rather than weaken isolation."""
    with lean_sandbox(check=False) as wrapper:
        return _probe(wrapper)


def main(*, scratch_root=None):
    try:
        arguments = sys.argv[1:]
        with tempfile.TemporaryDirectory(prefix="maam-lean-output-", dir=scratch_root) as folder:
            scratch = Path(folder)
            command = build_command(arguments, scratch=scratch)
            # close_fds prevents private inherited descriptors from reaching Lean;
            # --die-with-parent kills sandbox children if the verifier times us out.
            result = subprocess.run(command, close_fds=True, check=False)
            if result.returncode:
                return result.returncode
            if arguments not in (["--version"], ["--print-prefix"]):
                compile_command = arguments[1] == "-o"
                output = Path.cwd() / (arguments[2] if compile_command else arguments[3])
                generated = scratch / ("result.olean" if compile_command else "result.json")
                _regular_output(generated)
                if output.exists() or output.is_symlink():
                    _regular_output(output)
                # Never follow an output symlink, even if another local process races us.
                with generated.open("rb") as source:
                    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
                    with os.fdopen(fd, "wb") as dest:
                        while chunk := source.read(1024 * 1024):
                            dest.write(chunk)
            return 0
    except (OSError, ValueError, SandboxUnavailable) as exc:
        print("Lean sandbox refused: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
