"""Publish complete immutable assets, leaving channels unchanged on failure."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
import importlib.util

spec = importlib.util.spec_from_file_location('metadata', Path(__file__).with_name('release-metadata.py'))
metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metadata)


def run(*args):
    return subprocess.check_output(args, text=True)


def hashes(folder):
    result = {}
    for file in sorted(folder.iterdir()):
        if file.is_file():
            digest = hashlib.sha256()
            with file.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            result[file.name] = (file.stat().st_size, digest.hexdigest())
    return result


def publish(folder, repo, tool, unsigned=False):
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8-sig"))
    version = manifest["version"]
    import re
    if not re.fullmatch(r"0\.\d{6}\.\d+", version):
        raise RuntimeError("Invalid release version")
    metadata.validate(folder)
    if not unsigned:
        run(tool, "verify", "--dir", str(folder))
        if manifest.get('compatibility', {}).get('platform') == 'windows-x86_64':
            run(tool, "verify-install", "--dir", str(folder))
    tag = ("linux-unsigned-" if unsigned else "server-") + version
    # A retry may reuse a draft, but never modify a published release.
    found = subprocess.run(["gh", "release", "view", tag, "--repo", repo,
                            "--json", "isDraft"], capture_output=True, text=True)
    if found.returncode == 0:
        if not json.loads(found.stdout)["isDraft"]:
            raise RuntimeError(f"Immutable release {tag} already exists")
    else:
        # Abort on authentication/network errors, rather than treating all failures as absence.
        releases = json.loads(run("gh", "api", f"repos/{repo}/releases?per_page=100"))
        if any(release["tag_name"] == tag for release in releases):
            raise RuntimeError("Cannot inspect existing release")
        run("gh", "release", "create", tag, "--repo", repo, "--draft", "--prerelease",
            "--title", tag, "--notes", "Verified immutable candidate" + ("; unsigned Linux experimental" if unsigned else ""))
    for file in folder.iterdir():
        if file.is_file():
            run("gh", "release", "upload", tag, str(file), "--repo", repo, "--clobber")
    with tempfile.TemporaryDirectory() as temp:
        downloaded = Path(temp)
        run("gh", "release", "download", tag, "--repo", repo, "--dir", temp)
        if hashes(folder) != hashes(downloaded):
            raise RuntimeError("Remote release is incomplete or differs from the verified package")
        metadata.validate(downloaded)
        if not unsigned:
            run(tool, "verify", "--dir", temp)
            if manifest.get('compatibility', {}).get('platform') == 'windows-x86_64':
                run(tool, "verify-install", "--dir", temp)
    run("gh", "release", "edit", tag, "--repo", repo, "--draft=false")
    print(tag)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--tool", required=True)
    parser.add_argument("--unsigned", action="store_true")
    args = parser.parse_args()
    publish(args.dir, args.repo, args.tool, args.unsigned)
