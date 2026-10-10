"""Merge a daily candidate without updating the production coa-bots branch."""
import json
import os
import subprocess


def git(*args):
    return subprocess.check_output(["git", "-C", "_integration", *args], text=True).strip()


def main():
    git("config", "user.name", "coa-daily")
    git("config", "user.email", "coa-daily@users.noreply.github.com")
    git("fetch", "https://github.com/jealous-sound/azerothcore-wotlk-coa.git", "main")
    upstream = git("rev-parse", "FETCH_HEAD")
    git("merge", "--no-edit", upstream)
    release = json.loads(subprocess.check_output([
        "gh", "api", "repos/ilusixn/azerothcore-wotlk-coa/releases/latest"], text=True))
    git("fetch", "https://github.com/ilusixn/azerothcore-wotlk-coa.git", "refs/tags/" + release["tag_name"])
    git("merge", "--no-edit", git("rev-parse", "FETCH_HEAD"))
    # A new upstream module SQL path requires explicit adaptation into pending_db.
    new_paths = git("diff", "--name-only", "origin/coa-bots", "HEAD").splitlines()
    if any(p.startswith("modules/mod-coa-custom-races/data/sql/") for p in new_paths):
        raise RuntimeError("New race SQL needs migration review before release")
    remote = git("ls-remote", "origin", "refs/heads/feat/portable-session-bridge")
    if remote:
        excluded = remote.split()[0]
        git("fetch", "origin", excluded)
        ancestor = subprocess.run(["git", "-C", "_integration", "merge-base", "--is-ancestor", excluded, "HEAD"])
        if ancestor.returncode == 0:
            raise RuntimeError("Excluded portable bridge is present in candidate")
        if ancestor.returncode != 1:
            raise RuntimeError("Cannot verify portable bridge exclusion")
    sha = git("rev-parse", "HEAD")
    git("push", "origin", "HEAD:refs/heads/automation/daily-" + os.environ["GITHUB_RUN_ID"])
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write("core=" + sha + "\n")


if __name__ == "__main__":
    main()
