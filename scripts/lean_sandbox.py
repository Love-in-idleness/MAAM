#!/usr/bin/python3
"""Run pinned Lean with only its toolchain, checker and attempt directory visible."""
import os
from pathlib import Path
import pwd
import stat
import sys
import tempfile


SYSROOT = (Path(pwd.getpwuid(os.getuid()).pw_dir) / ".elan" / "toolchains"
           / "leanprover--lean4---v4.24.0")
CHECKER = Path(__file__).resolve().parents[1] / "maam" / "PackageCheck.lean"
BWRAP = "/usr/bin/bwrap"


def attempt_directory(cwd):
    directory = Path(cwd)
    info = directory.lstat()
    resolved = directory.resolve(strict=True)
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or resolved.parent != Path(tempfile.gettempdir()).resolve()
            or not resolved.name.startswith("maam-attempt-")):
        raise ValueError("compilation requires an owned, direct maam-attempt-* temporary directory")
    return resolved


def build_command(arguments, cwd=None):
    sysroot = SYSROOT.resolve(strict=True)
    checker = CHECKER.resolve(strict=True)
    executable = sysroot / "bin" / "lean"
    if not executable.is_file() or not checker.is_file():
        raise ValueError("the pinned Lean executable and package checker must exist")
    arguments = list(arguments)
    query = arguments in (["--version"], ["--print-prefix"])
    directory = None if query else attempt_directory(Path.cwd() if cwd is None else cwd)
    command = [BWRAP, "--unshare-all", "--die-with-parent", "--new-session", "--clearenv",
               "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin",
               "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
               "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
               "--ro-bind", str(sysroot), str(sysroot),
               "--ro-bind", str(checker), str(checker),
               "--setenv", "PATH", str(sysroot / "bin") + ":/usr/bin",
               "--setenv", "HOME", "/tmp", "--setenv", "TMPDIR", "/tmp",
               "--setenv", "LANG", "C.UTF-8"]
    if directory is not None:
        command += ["--bind", str(directory), str(directory),
                    "--setenv", "LEAN_PATH", str(directory), "--chdir", str(directory)]
    else:
        command += ["--chdir", "/"]
    return command + ["--", str(executable), *arguments]


def main():
    try:
        command = build_command(sys.argv[1:])
        # Replacing this process lets the evaluator's timeout kill bubblewrap directly.
        os.execv(BWRAP, command)
    except (OSError, ValueError) as exc:
        print("Lean sandbox refused: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
