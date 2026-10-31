import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


PIPELINE = Path(__file__).resolve().parents[1]


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], timeout=180)


def definition():
    value = json.loads((PIPELINE / "external-modules.json").read_text(encoding="utf-8"))
    if value.get("schema") != 1 or set(value["modules"]) != {"squid", "dungeon-clear"}:
        raise RuntimeError("Invalid external module source definition")
    for name, module in value["modules"].items():
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", module["repository"]):
            raise RuntimeError("Invalid external module repository: " + name)
        if not re.fullmatch("[a-f0-9]{40}", module["sha"]):
            raise RuntimeError("External modules require immutable source revisions")
        patch = (PIPELINE / module["patch"]).resolve()
        if not patch.is_relative_to(PIPELINE / "patches"):
            raise RuntimeError("External module patch escaped the pipeline")
        if hashlib.sha256(patch.read_bytes()).hexdigest() != module["patchSha256"]:
            raise RuntimeError("External module patch checksum differs: " + name)
    return value


def identity():
    return hashlib.sha256(json.dumps(definition(), sort_keys=True).encode()).hexdigest()


def prepare(core):
    value = definition()
    modules = core.resolve() / "modules"
    for name, module in value["modules"].items():
        path = modules / ("mod-playerbots" if name == "squid" else "mod-dungeon-clear")
        if not path.exists():
            if name == "squid":
                raise RuntimeError("Checkout the locked SQUID source before preparing external modules")
            path.mkdir(parents=True)
            git(path, "init")
            git(path, "remote", "add", "origin", "https://github.com/" + module["repository"] + ".git")
            git(path, "fetch", "--depth=1", "origin", module["sha"])
            git(path, "checkout", "--detach", "FETCH_HEAD")
        if git(path, "rev-parse", "HEAD").decode().strip() != module["sha"]:
            raise RuntimeError("External module revision needs compatibility review: " + name)
        patch = PIPELINE / module["patch"]
        changes = git(path, "diff", "--binary", "HEAD", "--")
        if changes:
            if changes != patch.read_bytes():
                raise RuntimeError("External module contains unexpected changes: " + name)
        else:
            git(path, "apply", "--check", str(patch))
            git(path, "apply", str(patch))
        print(f"{name} commit: {module['sha']}; CoA patch: {module['patchSha256']}", flush=True)
    print("external modules identity: " + identity(), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    prepare(parser.parse_args().core)
