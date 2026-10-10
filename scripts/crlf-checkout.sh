#!/usr/bin/env bash
# Rewrites the working tree of each given git checkout with Windows line endings (core.autocrlf=true), which is what a
# Windows runner checks out. The migration checksums recorded in the signed base package are those of CRLF files: the
# release SQL of the core, the modules and SQUID must be read the same way, or every applied migration looks edited.
# Only for the SQL checks and the package: the compile uses the untouched LF checkout. Usage: crlf-checkout.sh DIR...
set -euo pipefail
for d in "$@"; do
  git -C "$d" config core.autocrlf true
  git -C "$d" rm --cached -rq .
  git -C "$d" reset -q --hard
done
