#!/usr/bin/env bash
# Starts worldserver from an assembled package tree, in a clean Ubuntu 26.04, and checks that it reads its
# configuration from the package layout (Core/configs, started from Core/) and not from a path baked into the binary.
#
# There is no database, so worldserver stops soon after loading its configuration; that is enough to see which module
# configuration files it opened. Usage: smoke-test-linux.sh TREE
set -euo pipefail
tree=${1:?usage: $0 TREE}
fail() { echo "SMOKE TEST FAILED: $*" >&2; exit 1; }

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cp -r "$tree/." "$work/"
# The package holds only .dist files; the Manager creates the active ones. Do the same here.
for f in "$work"/Core/configs/*.conf.dist "$work"/Core/configs/modules/*.conf.dist; do cp "$f" "${f%.dist}"; done
# Negative control: this one is missing on purpose, so the log must report exactly it.
control=coa.conf
[ -f "$work/Core/configs/modules/$control" ] || fail "no $control in the package"
rm "$work/Core/configs/modules/$control"

log=$(docker run --rm -v "$work:/pkg" -w /pkg/Core ubuntu:26.04 sh -c '
  apt-get update -qq >/dev/null &&
  apt-get install -y -qq --no-install-recommends libmysqlclient24 libreadline8 libicu78 libncurses-dev >/dev/null 2>&1 &&
  timeout 30 ./worldserver -c configs/worldserver.conf 2>&1 || true' | sed 's/\x1b\[[0-9;]*m//g')

grep -q 'Using configuration file *configs/worldserver.conf' <<<"$log" || fail "worldserver did not report using configs/worldserver.conf"
grep -q 'Loading Modules Configuration' <<<"$log" || fail "worldserver never reached the module configuration step"

failed=$(sed -n "s/.*Failed open file '\(.*\)'.*/\1/p" <<<"$log")
outside=$(grep -v '^configs/modules/' <<<"$failed" || true)
[ -z "$outside" ] || fail "configuration looked up outside configs/modules/: $outside"
grep -qx "configs/modules/$control" <<<"$failed" || fail "the control file $control was not looked up in configs/modules/ (the loader does not read the package folder)"
for f in $(cd "$work/Core/configs/modules" && ls ./*.conf | sed 's#^\./##'); do
  ! grep -qx "configs/modules/$f" <<<"$failed" || fail "$f is in the package but worldserver could not open it"
done
echo "smoke test ok: module configuration is read from Core/configs/modules ($(ls "$work/Core/configs/modules"/*.conf | wc -l) files, control $control reported missing)"
