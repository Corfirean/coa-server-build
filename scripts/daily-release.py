"""Resolve a reproducible daily candidate; never compile from moving refs."""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


def gh(*args):
    return json.loads(subprocess.check_output(["gh", "api", *args], text=True))


def revision(repo, ref):
    return gh(f"repos/{repo}/commits/{ref}")["sha"]


def resolve(core_ref="coa-bots", manager_ref="master", bots_ref="master", scaling_ref="main", squid_ref="latest-release", upstream_ref="main", races_ref="latest-release"):
    races_path = "latest" if races_ref == "latest-release" else "tags/" + races_ref
    races = gh("repos/ilusixn/azerothcore-wotlk-coa/releases/" + races_path)
    tags = gh("repos/Zyth45/mod-playerbots/tags?per_page=100")
    import re
    stable = [t for t in tags if re.fullmatch(r"v\d+\.\d+(?:\.\d+)?", t["name"])]
    if not stable:
        raise RuntimeError("No stable SQUID source tag found")
    squid = max(stable, key=lambda t: tuple(map(int, t["name"][1:].split("."))))
    components = {
        "upstream": {"repository": "jealous-sound/azerothcore-wotlk-coa", "ref": upstream_ref},
        "core": {"repository": "Corfirean/azerothcore-wotlk-coa", "ref": core_ref},
        "bots": {"repository": "Corfirean/mod-coa-playerbots", "ref": bots_ref},
        "scaling": {"repository": "Corfirean/mod-coa-content-scaling", "ref": scaling_ref},
        "manager": {"repository": "Corfirean/coa-server-manager", "ref": manager_ref},
        "races": {"repository": "ilusixn/azerothcore-wotlk-coa", "ref": races["tag_name"]},
        "squid": {"repository": "Zyth45/mod-playerbots", "ref": squid["name"] if squid_ref == 'latest-release' else squid_ref},
    }
    pipeline_sha = os.environ.get('GITHUB_SHA') or subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    components['build'] = {'repository': 'Corfirean/coa-server-build', 'ref': pipeline_sha}
    for component in components.values():
        component["sha"] = revision(component["repository"], component["ref"])
    components['squid']['ref'] = next((t['name'] for t in stable
                                     if t['commit']['sha'] == components['squid']['sha']), components['squid']['ref'])
    components["races"]["assets"] = [
        {"name": asset["name"], "size": asset["size"], "digest": asset.get("digest"),
         "url": asset["browser_download_url"]} for asset in races["assets"]
    ]
    if any(not a["digest"] or not a["digest"].startswith("sha256:")
           for a in components["races"]["assets"]):
        raise RuntimeError("Custom race assets need SHA256 digests before release")
    navigation = Path(__file__).resolve().parent.parent / 'navigation-source.json'
    if navigation.exists():
        components['navigation'] = json.loads(navigation.read_text(encoding='utf-8'))
    lock = {"schema": 1, "components": components,
            "excludedBranches": ["feat/portable-characters", "feat/portable-session-bridge"]}
    lock["snapshot"] = snapshot(components)
    return lock


def snapshot(components):
    identity = {name: {k: v for k, v in component.items() if k != 'ref'}
                for name, component in components.items()}
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


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
    parser.add_argument("--manager-ref", default="master")
    parser.add_argument("--bots-ref", default="master")
    parser.add_argument("--scaling-ref", default="main")
    parser.add_argument("--squid-ref", default="latest-release")
    parser.add_argument("--upstream-ref", default="main")
    args = parser.parse_args()
    lock = resolve(args.core_ref, args.manager_ref, args.bots_ref, args.scaling_ref, args.squid_ref, args.upstream_ref)
    Path(args.out).write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    if args.check_integration:
        check_integration(lock)
    print(lock["snapshot"])


if __name__ == "__main__":
    main()
