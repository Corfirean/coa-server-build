"""Resolve a reproducible daily candidate; never compile from moving refs."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def gh(*args):
    return json.loads(subprocess.check_output(["gh", "api", *args], text=True))


def revision(repo, ref):
    return gh(f"repos/{repo}/commits/{ref}")["sha"]


def resolve(core_ref="coa-bots"):
    races = gh("repos/ilusixn/azerothcore-wotlk-coa/releases/latest")
    tags = gh("repos/Zyth45/mod-playerbots/tags?per_page=100")
    import re
    stable = [t for t in tags if re.fullmatch(r"v\d+\.\d+(?:\.\d+)?", t["name"])]
    if not stable:
        raise RuntimeError("No stable SQUID source tag found")
    squid = max(stable, key=lambda t: tuple(map(int, t["name"][1:].split("."))))
    components = {
        "upstream": {"repository": "jealous-sound/azerothcore-wotlk-coa", "ref": "main"},
        "core": {"repository": "Corfirean/azerothcore-wotlk-coa", "ref": core_ref},
        "bots": {"repository": "Corfirean/mod-coa-playerbots", "ref": "master"},
        "scaling": {"repository": "Corfirean/mod-coa-content-scaling", "ref": "main"},
        "manager": {"repository": "Corfirean/coa-server-manager", "ref": "master"},
        "races": {"repository": "ilusixn/azerothcore-wotlk-coa", "ref": races["tag_name"]},
        "squid": {"repository": "Zyth45/mod-playerbots", "ref": squid["name"]},
    }
    for component in components.values():
        component["sha"] = revision(component["repository"], component["ref"])
    components["races"]["assets"] = [
        {"name": asset["name"], "size": asset["size"], "digest": asset.get("digest"),
         "url": asset["browser_download_url"]} for asset in races["assets"]
    ]
    if any(not a["digest"] or not a["digest"].startswith("sha256:")
           for a in components["races"]["assets"]):
        raise RuntimeError("Custom race assets need SHA256 digests before release")
    lock = {"schema": 1, "components": components,
            "excludedBranches": ["feat/portable-characters", "feat/portable-session-bridge"]}
    identity = {name: {k: v for k, v in component.items() if k != "ref"}
                for name, component in components.items()}
    lock["snapshot"] = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return lock


def check_integration(lock):
    core = lock["components"]["core"]
    for name in ("upstream", "races"):
        sha = lock["components"][name]["sha"]
        comparison = gh(f"repos/{core['repository']}/compare/{sha}...{core['sha']}")
        if comparison["status"] not in ("ahead", "identical"):
            raise RuntimeError(f"{name} {sha} has not been integrated into coa-bots")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="release-lock.json")
    parser.add_argument("--check-integration", action="store_true")
    parser.add_argument("--core-ref", default="coa-bots")
    args = parser.parse_args()
    lock = resolve(args.core_ref)
    Path(args.out).write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    if args.check_integration:
        check_integration(lock)
    print(lock["snapshot"])


if __name__ == "__main__":
    main()
