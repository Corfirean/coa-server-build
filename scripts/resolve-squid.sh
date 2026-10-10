#!/usr/bin/env bash
# Linux counterpart of resolve-squid.ps1: resolves the SQUID source to an exact commit.
# 'latest-release' selects the highest stable numeric v* tag; any other ref is resolved as given.
# Prints squid_sha=... and squid_tag=... (and appends them to $GITHUB_OUTPUT when it is set). Needs gh and GH_TOKEN.
set -euo pipefail
ref=${1:-latest-release}
repo=Zyth45/mod-playerbots
if [ "$ref" = latest-release ]; then
  tag=$(gh api "repos/$repo/tags" --paginate --jq '.[].name' | grep -E '^v[0-9]+\.[0-9]+(\.[0-9]+)?$' | sort -V | tail -n 1 || true)
  [ -n "$tag" ] || { echo 'No stable SQUID v* release tag was found.' >&2; exit 1; }
  sha=$(gh api "repos/$repo/commits/$tag" --jq .sha)
else
  sha=$(gh api "repos/$repo/commits/$(jq -rn --arg r "$ref" '$r|@uri')" --jq .sha) || { echo 'Cannot resolve the requested SQUID source.' >&2; exit 1; }
  if [[ "$ref" =~ ^v[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then tag=$ref; else tag=; fi
fi
[[ "$sha" =~ ^[a-f0-9]{40}$ ]] || { echo 'Invalid resolved SQUID commit.' >&2; exit 1; }
echo "squid_sha=$sha"
echo "squid_tag=$tag"
if [ -n "${GITHUB_OUTPUT:-}" ]; then { echo "squid_sha=$sha"; echo "squid_tag=$tag"; } >> "$GITHUB_OUTPUT"; fi
