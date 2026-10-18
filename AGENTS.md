# Server build and release workflow

Read [the release runbook](docs/server-release.md) before integrating sources, compiling, packaging, publishing or
promoting a server. It defines the repositories, frozen source lock, verification gates and handoff information.

Preparation and publication are separate actions. When the owner asks to build and release later on command, dispatch
`build.yml` with `publish_candidate=false`. A successful build leaves a signed, qualified artifact; it is not permission
to publish a GitHub release or update `stable`. Publish and promote only after the owner's explicit instruction for the
identified candidate. Never substitute the latest moving branch for its frozen SHAs when resuming another agent's work.

Use existing tests with `python -B -m unittest discover -s scripts -p "test_*.py"` and actionlint for changed workflows.
Server source verification must follow that repository's AGENTS.md and `tools/verify_all.py`.

Preserve unrelated work. Do not overwrite a primary core checkout to integrate a release; use an isolated branch.
Do not print signing keys or GitHub runner registration tokens. Do not weaken qualification to make a release pass.
