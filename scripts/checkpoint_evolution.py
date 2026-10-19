#!/usr/bin/env python3
"""Save immutable complete controller checkpoints outside its temporary root."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maam.evolution import run_record
from maam.independent import bundle, now, restore_bundle
from maam.migration import save_new, seal, unseal
from maam.corpus import CorpusError


def checkpoint(root, directory, label):
    root, directory = Path(root).resolve(), Path(directory).resolve()
    if directory == root or root in directory.parents:
        raise CorpusError("checkpoint storage must be outside the controller root")
    run_record(root)
    directory.mkdir(parents=True, exist_ok=True)
    index = len(list(directory.glob("checkpoint-*.json"))) + 1
    path = directory / f"checkpoint-{index:04d}.json"
    save_new(path, seal({"schema_version": 1, "created_at": now(), "label": label,
                        "controller": bundle(root)}))
    return path


def recover(path, root):
    value = unseal(Path(path))
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    restore_bundle(value["controller"], root)
    run_record(root)
    return root


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--label", default="manual")
    parser.add_argument("--restore", type=Path)
    args = parser.parse_args()
    if args.restore:
        print(recover(args.restore, args.root))
    elif args.directory:
        print(checkpoint(args.root, args.directory, args.label))
    else:
        parser.error("supply --directory or --restore")
