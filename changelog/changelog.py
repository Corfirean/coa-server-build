#!/usr/bin/env python3
"""One changelog for every CoA project (server fork, bots, Content Scaling, Manager, renderer).

Every repository keeps small fragment files in `changelog.d/` (one per change a player or server owner would notice).
This tool, which lives in coa-server-build, validates them, collects them from all repositories, and at release time
writes CHANGELOG.md, the Discord text and changelog.json. Standard library only.

    changelog.py new --area bots --type fixed --audience players --title "..." [--body "..."]   (in a repository)
    changelog.py check [--dir changelog.d] | [--remote] [--source NAME=PATH ...]
    changelog.py status [--remote] [--source NAME=PATH ...]
    changelog.py release --id 2026-10-03 [--server V] [--manager V] [--addon V] [--renderer V] [--dry-run]
    changelog.py render
    changelog.py discord ID
    changelog.py sync-instructions PATH [PATH ...] [--bottom]

See changelog/GUIDE.md for the format and the rules.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RELEASES_DIR = HERE / "releases"
DISCORD_DIR = HERE / "discord"
SOURCES_FILE = HERE / "sources.json"

AREAS = {
    "server": "Server",
    "bots": "Companion bots",
    "scaling": "Content Scaling",
    "modules": "Server modules",
    "manager": "Manager",
    "addon": "Bot UI addon",
    "client": "Game client",
    "renderer": "Modern WoW Renderer",
}
TYPES = ["added", "changed", "fixed", "removed", "known-issue"]
TYPE_LABEL = {"added": "Added", "changed": "Changed", "fixed": "Fixed", "removed": "Removed", "known-issue": "Known issue"}
AUDIENCES = ["players", "admins"]
AUDIENCE_LABEL = {"players": "For players", "admins": "For server owners"}
VERSION_KEYS = [("server", "Server"), ("manager", "Manager"), ("bots", "Bots"), ("addon", "Addon"), ("renderer", "Renderer")]
COMPONENT_AREAS = {
    "manager": {"manager"},
    "bots": {"bots", "addon"},
    "server": {"server", "bots", "scaling", "modules", "addon", "client"},
}

FILENAME_RE = re.compile(r"^(\d{8})-([a-z0-9][a-z0-9-]{1,60})\.md$")
ALLOWED_KEYS = {"area", "type", "audience", "title", "refs"}
NON_ENGLISH_RE = re.compile("[Ѐ-ӿ぀-ヿ㐀-鿿가-힯]")
INTERNAL_HINT_RE = re.compile(r"\b(refactor\w*|unit tests?|lint\w*|ci pipeline|cleanup|clean-up|typo)\b", re.I)
TITLE_MAX = 90
BODY_MAX = 300
DISCORD_LIMIT = 1900


# ----------------------------------------------------------------------------------------------------------------- model
@dataclass
class Fragment:
    source: str
    repo: str
    filename: str
    area: str = ""
    type: str = ""
    audience: str = ""
    title: str = ""
    body: str = ""
    refs: str = ""
    date: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.source}:{self.filename}"

    def as_entry(self) -> dict:
        entry = {
            "id": self.id,
            "source": self.source,
            "repo": self.repo,
            "date": self.date,
            "area": self.area,
            "type": self.type,
            "audience": self.audience,
            "title": self.title,
        }
        if self.body:
            entry["body"] = self.body
        if self.refs:
            entry["refs"] = self.refs
        return entry


def parse_fragment(source: str, repo: str, filename: str, text: str) -> Fragment:
    """Parse and validate one fragment file; problems are collected in .errors / .warnings (never raised)."""
    f = Fragment(source=source, repo=repo, filename=filename)
    m = FILENAME_RE.match(filename)
    if not m:
        f.errors.append("file name must look like YYYYMMDD-short-slug.md (lowercase letters, digits, dashes)")
    else:
        try:
            d = dt.datetime.strptime(m.group(1), "%Y%m%d").date()
            f.date = d.isoformat()
        except ValueError:
            f.errors.append("the date at the start of the file name is not a real date")
    text = text.lstrip("﻿").replace("\r\n", "\n")
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        f.errors.append("the file must start with a front-matter block: a line with --- , the keys, another line with ---")
        return f
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        f.errors.append("the front-matter block is not closed with a second --- line")
        return f
    meta: dict[str, str] = {}
    for raw in lines[1:end]:
        if not raw.strip():
            continue
        if ":" not in raw:
            f.errors.append(f"front-matter line without a colon: {raw.strip()!r}")
            continue
        k, v = raw.split(":", 1)
        k = k.strip().lower()
        if k not in ALLOWED_KEYS:
            f.errors.append(f"unknown key {k!r} (allowed: {', '.join(sorted(ALLOWED_KEYS))})")
            continue
        meta[k] = v.strip().strip('"').strip("'")
    f.area, f.type, f.audience, f.title, f.refs = (meta.get(k, "") for k in ("area", "type", "audience", "title", "refs"))
    if f.area not in AREAS:
        f.errors.append(f"area must be one of: {', '.join(AREAS)} (got {f.area!r})")
    if f.type not in TYPES:
        f.errors.append(f"type must be one of: {', '.join(TYPES)} (got {f.type!r})")
    if f.audience not in AUDIENCES:
        f.errors.append(f"audience must be one of: {', '.join(AUDIENCES)} (got {f.audience!r})")
    if not f.title:
        f.errors.append("title is required")
    else:
        if len(f.title) > TITLE_MAX:
            f.errors.append(f"title is {len(f.title)} characters, the limit is {TITLE_MAX}")
        if len(f.title) < 8:
            f.errors.append("title is too short to mean anything on its own")
        if f.title.endswith("."):
            f.errors.append("title must not end with a full stop")
        if f.title[0].islower():
            f.errors.append("title must start with a capital letter")
        if NON_ENGLISH_RE.search(f.title):
            f.errors.append("title must be in English")
        if INTERNAL_HINT_RE.search(f.title):
            f.warnings.append("this looks like an internal change; the changelog is for things players or server owners notice")
    body = "\n".join(lines[end + 1:]).strip()
    if "\n\n" in body:
        f.errors.append("the body must be a single paragraph (no blank lines)")
    body = " ".join(body.split())
    if len(body) > BODY_MAX:
        f.errors.append(f"body is {len(body)} characters, the limit is {BODY_MAX}")
    if NON_ENGLISH_RE.search(body):
        f.errors.append("body must be in English")
    f.body = body
    return f


# ------------------------------------------------------------------------------------------------------------- sources
def load_sources() -> list[dict]:
    return json.loads(SOURCES_FILE.read_text(encoding="utf-8"))["sources"]


def _gh_api(path: str, raw: bool = False) -> bytes:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if shutil.which("gh") and not token:
        cmd = ["gh", "api"] + (["-H", "Accept: application/vnd.github.raw"] if raw else []) + [path]
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode("utf-8", "replace").strip() or f"gh api {path} failed")
        return r.stdout
    req = urllib.request.Request(f"https://api.github.com/{path}")
    req.add_header("Accept", "application/vnd.github.raw" if raw else "application/vnd.github+json")
    req.add_header("User-Agent", "coa-changelog")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GitHub answered {e.code} for {path}") from e


def fetch_remote(src: dict) -> list[Fragment]:
    repo, branch = src["repo"], src.get("branch", "main")
    try:
        listing = json.loads(_gh_api(f"repos/{repo}/contents/changelog.d?ref={branch}"))
    except RuntimeError as e:
        if "404" in str(e) or "Not Found" in str(e):
            return []  # no changelog.d yet: nothing to collect
        raise
    out = []
    for item in listing:
        name = item["name"]
        if item["type"] != "file" or not name.endswith(".md") or name.lower() == "readme.md":
            continue
        text = _gh_api(f"repos/{repo}/contents/changelog.d/{name}?ref={branch}", raw=True).decode("utf-8")
        out.append(parse_fragment(src["name"], repo, name, text))
    return out


def read_local(name: str, repo: str, directory: Path) -> list[Fragment]:
    out = []
    if not directory.is_dir():
        return out
    for p in sorted(directory.glob("*.md")):
        if p.name.lower() == "readme.md":
            continue
        out.append(parse_fragment(name, repo, p.name, p.read_text(encoding="utf-8")))
    return out


def collect(remote: bool, overrides: dict[str, Path]) -> list[Fragment]:
    frags: list[Fragment] = []
    for src in load_sources():
        if src["name"] in overrides:
            frags += read_local(src["name"], src["repo"], overrides[src["name"]])
        elif remote:
            frags += fetch_remote(src)
    for name, path in overrides.items():
        if name not in {s["name"] for s in load_sources()}:
            frags += read_local(name, name, path)
    return frags


def collect_locked(path: Path) -> list[Fragment]:
    lock = json.loads(path.read_text(encoding="utf-8"))
    components = lock["components"]
    aliases = {"server": "core", "bots": "bots", "scaling": "scaling", "manager": "manager", "build": "build"}
    fragments = []
    for name, key in aliases.items():
        if key not in components:
            continue
        component = components[key]
        sha = component["sha"]
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError(f"{key}: changelog source is not pinned")
        fragments.extend(fetch_remote({"name": name, "repo": component["repository"], "branch": sha}))
    return fragments


# ------------------------------------------------------------------------------------------------------------ releases
def load_releases() -> list[dict]:
    if not RELEASES_DIR.is_dir():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(RELEASES_DIR.glob("*.json"))]


def released_ids(releases: list[dict], component: str | None = None) -> set[str]:
    return {e["id"] for r in releases if component is None or r.get("component") in (None, component)
            for e in r["entries"]}


def sort_entries(entries: list[dict]) -> list[dict]:
    area_order = list(AREAS)
    return sorted(entries, key=lambda e: (AUDIENCES.index(e["audience"]), area_order.index(e["area"]), TYPES.index(e["type"]), e["date"], e["id"]))


# -------------------------------------------------------------------------------------------------------------- render
def version_line(versions: dict) -> str:
    parts = [f"{label} {versions[k]}" for k, label in VERSION_KEYS if versions.get(k)]
    return " · ".join(parts)


def _sentence(e: dict) -> str:
    return e["title"] if not e.get("body") else f"{e['title']}. {e['body']}"


def group(entries: list[dict]):
    """audience -> area -> [entries], in the display order."""
    out: dict[str, dict[str, list[dict]]] = {}
    for e in sort_entries(entries):
        out.setdefault(e["audience"], {}).setdefault(e["area"], []).append(e)
    return out


def render_release_md(r: dict) -> str:
    head = f"## {r['id']}" + (f" - {version_line(r['versions'])}" if version_line(r["versions"]) else "")
    lines = [head, ""]
    for audience, areas in group(r["entries"]).items():
        lines += [f"### {AUDIENCE_LABEL[audience]}", ""]
        for area, items in areas.items():
            lines += [f"**{AREAS[area]}**", ""]
            for e in items:
                tag = "Known issue" if e["type"] == "known-issue" else TYPE_LABEL[e["type"]]
                lines.append(f"- {tag}: {_sentence(e)}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_changelog_md(releases: list[dict]) -> str:
    out = ["# Changelog", "",
           "Everything that changed for players and server owners across the CoA server, bots, Content Scaling, the Manager and the renderer, newest first.",
           "Written from the `changelog.d/` fragments of each repository (see `changelog/GUIDE.md`).", ""]
    for r in sorted(releases, key=lambda r: r["id"], reverse=True):
        out.append(render_release_md(r))
    return "\n".join(out).rstrip() + "\n"


def render_discord(r: dict) -> list[str]:
    """Messages of at most DISCORD_LIMIT characters, split between sections (never inside a bullet)."""
    blocks: list[str] = []
    for audience, areas in group(r["entries"]).items():
        for area, items in areas.items():
            title = f"**{AREAS[area]}**" + (" (for server owners)" if audience == "admins" else "")
            bullets = []
            for e in items:
                tag = "Known" if e["type"] == "known-issue" else TYPE_LABEL[e["type"]]
                bullets.append(f"- {tag}: {_sentence(e)}")
            blocks.append(title + "\n" + "\n".join(bullets))
    header = f"**Update {r['id']}**" + (f" ({version_line(r['versions'])})" if version_line(r["versions"]) else "")
    messages: list[str] = []
    cur = header
    for b in blocks:
        if len(b) > DISCORD_LIMIT:  # one huge section: split by bullets
            head, *bl = b.split("\n")
            piece = head
            for line in bl:
                if len(piece) + 1 + len(line) > DISCORD_LIMIT:
                    messages.append(piece)
                    piece = head + " (cont.)"
                piece += "\n" + line
            b = piece
        if len(cur) + 2 + len(b) > DISCORD_LIMIT:
            messages.append(cur)
            cur = b
        else:
            cur = cur + "\n\n" + b
    messages.append(cur)
    return messages


def write_outputs(releases: list[dict]) -> None:
    (ROOT / "CHANGELOG.md").write_text(render_changelog_md(releases), encoding="utf-8", newline="\n")
    (HERE / "changelog.json").write_text(
        json.dumps({"schema": 1, "releases": sorted(releases, key=lambda r: r["id"], reverse=True)}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    DISCORD_DIR.mkdir(exist_ok=True)
    for r in releases:
        msgs = render_discord(r)
        text = ("\n\n----- next message -----\n\n").join(msgs) + "\n"
        (DISCORD_DIR / f"{r['id']}.txt").write_text(text, encoding="utf-8", newline="\n")


# ------------------------------------------------------------------------------------------------------------ commands
def parse_overrides(items: list[str] | None) -> dict[str, Path]:
    out = {}
    for it in items or []:
        if "=" not in it:
            raise SystemExit(f"--source needs NAME=PATH, got {it!r}")
        n, p = it.split("=", 1)
        out[n] = Path(p)
    return out


def report(frags: list[Fragment]) -> int:
    bad = 0
    for f in frags:
        for m in f.errors:
            print(f"ERROR   {f.id}: {m}")
        for m in f.warnings:
            print(f"warning {f.id}: {m}")
        bad += bool(f.errors)
    ids: dict[str, int] = {}
    for f in frags:
        ids[f.id] = ids.get(f.id, 0) + 1
    print(f"{len(frags)} fragment(s), {bad} with errors")
    return 1 if bad else 0


def cmd_check(a) -> int:
    if a.dir:
        d = Path(a.dir)
        if not d.is_dir():
            print(f"{d} does not exist: nothing to check")
            return 0
        return report(read_local(a.name or d.resolve().parent.name, a.name or "local", d))
    return report(collect(a.remote, parse_overrides(a.source)))


def cmd_status(a) -> int:
    frags = collect(a.remote, parse_overrides(a.source))
    done = released_ids(load_releases())
    fresh = [f for f in frags if f.id not in done]
    rc = report(frags)
    print(f"\nUnreleased: {len(fresh)}")
    for f in fresh:
        if not f.errors:
            print(f"  [{f.audience}/{f.area}/{f.type}] {f.title}   ({f.id})")
    return rc


def cmd_release(a) -> int:
    lock = getattr(a, "lock", None)
    frags = collect_locked(Path(lock)) if lock else collect(a.remote or not a.source, parse_overrides(a.source))
    component = getattr(a, "component", None)
    if component:
        frags = [f for f in frags if f.area in COMPONENT_AREAS[component]]
    if report(frags):
        print("Fix the errors above first; nothing was released.")
        return 1
    releases = load_releases()
    if any(r["id"] == a.id for r in releases):
        print(f"release {a.id} already exists")
        return 1
    done = released_ids(releases, component)
    fresh = [f for f in frags if f.id not in done and (component is None or f.area in COMPONENT_AREAS[component])]
    if not fresh:
        print("Nothing unreleased.")
        return 1
    versions = {k: getattr(a, k) for k, _ in VERSION_KEYS if getattr(a, k, None)}
    date = a.date or (re.search(r"\d{4}-\d{2}-\d{2}", a.id).group() if re.search(r"\d{4}-\d{2}-\d{2}", a.id) else dt.date.today().isoformat())
    record = {"id": a.id, "date": date, "versions": versions, "entries": [f.as_entry() for f in sort_entries_frag(fresh)]}
    if lock:
        record["snapshot"] = json.loads(Path(lock).read_text(encoding="utf-8"))["snapshot"]
    if component:
        record["component"] = component
    if a.dry_run:
        print(render_release_md(record))
        print("--- Discord ---")
        print(("\n\n----- next message -----\n\n").join(render_discord(record)))
        return 0
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    (RELEASES_DIR / f"{a.id}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    write_outputs(load_releases())
    print(f"Release {a.id}: {len(fresh)} entries. Wrote CHANGELOG.md, changelog/changelog.json and changelog/discord/{a.id}.txt")
    return 0


def sort_entries_frag(frags: list[Fragment]) -> list[Fragment]:
    by_id = {f.id: f for f in frags}
    return [by_id[e["id"]] for e in sort_entries([f.as_entry() for f in frags])]


def cmd_render(_a) -> int:
    write_outputs(load_releases())
    print("Rendered CHANGELOG.md, changelog/changelog.json and the Discord texts.")
    return 0


def cmd_discord(a) -> int:
    for r in load_releases():
        if r["id"] == a.id:
            print(("\n\n----- next message -----\n\n").join(render_discord(r)))
            return 0
    print(f"no release {a.id}")
    return 1


def slugify(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:48].strip("-") or "change"


def cmd_new(a) -> int:
    date = (a.date or dt.date.today().isoformat()).replace("-", "")
    name = f"{date}-{slugify(a.title)}.md"
    body = a.body or ""
    text = f"---\narea: {a.area}\ntype: {a.type}\naudience: {a.audience}\ntitle: {a.title}\n---\n" + (body + "\n" if body else "")
    frag = parse_fragment("local", "local", name, text)
    if frag.errors:
        for m in frag.errors:
            print(f"ERROR: {m}")
        return 1
    d = Path(a.dir)
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    if p.exists():
        print(f"{p} exists already")
        return 1
    p.write_text(text, encoding="utf-8", newline="\n")
    for m in frag.warnings:
        print(f"warning: {m}")
    print(f"wrote {p}")
    return 0


SNIPPET_START = "<!-- changelog:start (managed by coa-server-build/changelog/changelog.py sync-instructions) -->"
SNIPPET_END = "<!-- changelog:end -->"


def snippet() -> str:
    return (HERE / "agents-snippet.md").read_text(encoding="utf-8").strip()


def _put_snippet(path: Path, bottom: bool, header: str = "") -> str:
    block = f"{SNIPPET_START}\n{snippet()}\n{SNIPPET_END}"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    nl = "\r\n" if "\r\n" in text else "\n"
    text = text.replace("\r\n", "\n")
    if SNIPPET_START in text and SNIPPET_END in text:
        pre, rest = text.split(SNIPPET_START, 1)
        _, post = rest.split(SNIPPET_END, 1)
        new = pre + block + post
        action = "updated"
    elif not text.strip():
        new = (header + "\n\n" if header else "") + block + "\n"
        action = "created"
    elif bottom:
        new = text.rstrip("\n") + "\n\n" + block + "\n"
        action = "appended to"
    else:
        lines = text.split("\n")
        at = next((i for i, l in enumerate(lines) if l.startswith("## ")), len(lines))
        new = "\n".join(lines[:at]) .rstrip("\n") + "\n\n" + block + "\n\n" + "\n".join(lines[at:]).lstrip("\n")
        action = "inserted into"
    path.write_text(new.replace("\n", nl), encoding="utf-8", newline="")
    return action


def cmd_sync(a) -> int:
    for p in a.paths:
        repo = Path(p)
        if not repo.is_dir():
            print(f"{repo}: not a directory")
            return 1
        print(f"{repo}: AGENTS.md {_put_snippet(repo / 'AGENTS.md', a.bottom, '# AGENTS.md')}")
        for name in ("CLAUDE.md", "GEMINI.md"):
            f = repo / name
            if not f.exists() or not f.read_text(encoding="utf-8").strip():
                f.write_text("@AGENTS.md\n", encoding="utf-8", newline="\n")
                print(f"{repo}: {name} created (imports AGENTS.md)")
        d = repo / "changelog.d"
        d.mkdir(exist_ok=True)
        readme = d / "README.md"
        readme.write_text((HERE / "fragments-readme.md").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new", help="create a fragment in ./changelog.d")
    p.add_argument("--area", required=True, choices=list(AREAS))
    p.add_argument("--type", required=True, choices=TYPES)
    p.add_argument("--audience", required=True, choices=AUDIENCES)
    p.add_argument("--title", required=True)
    p.add_argument("--body")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p.add_argument("--dir", default="changelog.d")
    p.set_defaults(fn=cmd_new)

    for name, fn in (("check", cmd_check), ("status", cmd_status)):
        p = sub.add_parser(name)
        p.add_argument("--dir", help="check one repository's changelog.d folder")
        p.add_argument("--name")
        p.add_argument("--remote", action="store_true", help="read the fragments from GitHub")
        p.add_argument("--source", action="append", help="NAME=PATH of a local changelog.d (overrides GitHub for that source)")
        p.set_defaults(fn=fn)

    p = sub.add_parser("release")
    p.add_argument("--lock", type=Path, help="Collect only revisions from this release-lock.json")
    p.add_argument("--component", choices=list(COMPONENT_AREAS), help="Release only this component's changes")
    p.add_argument("--id", required=True, help="release id, usually the date: 2026-10-03 (add -2 for a second one the same day)")
    p.add_argument("--date")
    for k, _ in VERSION_KEYS:
        p.add_argument(f"--{k}")
    p.add_argument("--remote", action="store_true")
    p.add_argument("--source", action="append")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_release)

    sub.add_parser("render").set_defaults(fn=cmd_render)
    p = sub.add_parser("discord")
    p.add_argument("id")
    p.set_defaults(fn=cmd_discord)
    p = sub.add_parser("sync-instructions")
    p.add_argument("paths", nargs="+")
    p.add_argument("--bottom", action="store_true", help="append the section at the end of AGENTS.md instead of before its first ## heading")
    p.set_defaults(fn=cmd_sync)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
