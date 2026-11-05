"""Merge a daily candidate without updating the production coa-bots branch."""
import json
import os
import subprocess
from pathlib import Path


def git(*args):
    command = ["git", "-C", "_integration", *args]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.stdout:
        print(result.stdout, end='' if result.stdout.endswith('\n') else '\n', flush=True)
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, command, output=result.stdout)
    return result.stdout.strip()


def record_failure(error):
    def inspect(*args):
        result = subprocess.run(['git', '-C', '_integration', *args], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else ''
    details = {'error': str(error), 'command': getattr(error, 'cmd', []),
               'output': getattr(error, 'output', None) or str(error),
               'conflicts': inspect('diff', '--name-only', '--diff-filter=U').splitlines(),
               'status': inspect('status', '--short')}
    Path('integration-diagnostics.json').write_text(json.dumps(details, indent=2) + '\n', encoding='utf-8')


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
    try:
        main()
    except Exception as error:
        record_failure(error)
        raise
