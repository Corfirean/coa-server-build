# Server build and release workflow

Public changelogs are component-scoped: this repository's `CHANGELOG.md` is server-only;
Manager maintains its own `CHANGELOG.md`. Read `changelog/GUIDE.md`. Publish only changes present in
the immutable released sources, never pending Manager features or moving-branch fragments. The
automatic changelog workflow synchronizes the reviewed `changelog/history.json`, Markdown and
GitHub release notes. Legacy combined records are archived and must not be used as current notes.

Read [the release runbook](docs/server-release.md) before integrating sources, compiling, packaging, publishing or
promoting a server. It defines the repositories, frozen source lock, verification gates and handoff information.

Preparation and publication are separate actions. When the owner asks to build and release later on command, dispatch
`build.yml` with `publish_candidate=false`. A successful build leaves a signed, qualified artifact; it is not permission
to publish a GitHub release or update `stable`. A normal owner instruction to release the identified candidate
authorizes both publication and stable promotion; finish both without asking the same permission again. Stop at
Pre-release only when the owner specifically requests a candidate, prerelease or preparation only. Never substitute
the latest moving branch for its frozen SHAs when resuming another agent's work.

Before rebuilding, recover the existing run, signed artifacts and handoff. Use the persistent Windows runner and
cached promotion workflow. Read the runbook's completion checklist: a successful build or GitHub release alone is
not a completed stable release. Keep local acceptance honest and preserve production databases.

Use existing tests with `python -B -m unittest discover -s scripts -p "test_*.py"` and actionlint for changed workflows.
Server source verification must follow that repository's AGENTS.md and `tools/verify_all.py`.

Preserve unrelated work. Do not overwrite a primary core checkout to integrate a release; use an isolated branch.
Do not print signing keys or GitHub runner registration tokens. Do not weaken qualification to make a release pass.
