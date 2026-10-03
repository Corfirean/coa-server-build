import json
import shutil
import tempfile
import unittest
from pathlib import Path

import changelog as cl

GOOD = "---\narea: bots\ntype: added\naudience: players\ntitle: Invite one bot by role\n---\nPick a role and a free bot joins your group.\n"


class Parse(unittest.TestCase):
    def p(self, text, name="20261003-invite-bot.md"):
        return cl.parse_fragment("bots", "x/y", name, text)

    def test_a_good_fragment_has_no_problems(self):
        f = self.p(GOOD)
        self.assertEqual(f.errors, [])
        self.assertEqual((f.area, f.type, f.audience, f.date), ("bots", "added", "players", "2026-10-03"))
        self.assertEqual(f.body, "Pick a role and a free bot joins your group.")

    def test_crlf_and_bom_are_accepted(self):
        self.assertEqual(self.p("﻿" + GOOD.replace("\n", "\r\n")).errors, [])

    def test_every_rule_is_reported(self):
        bad = {
            "no front matter": "title: x\n",
            "unclosed": "---\narea: bots\n",
            "unknown key": GOOD.replace("title:", "headline:"),
            "bad area": GOOD.replace("area: bots", "area: stuff"),
            "bad type": GOOD.replace("type: added", "type: new"),
            "bad audience": GOOD.replace("players", "everyone"),
            "no title": GOOD.replace("title: Invite one bot by role\n", ""),
            "full stop": GOOD.replace("by role", "by role."),
            "lowercase": GOOD.replace("Invite", "invite"),
            "russian": GOOD.replace("Invite one bot by role", "Кнопка приглашения"),
            "long title": GOOD.replace("Invite one bot by role", "A" * 95),
            "two paragraphs": GOOD + "\nSecond paragraph.\n",
            "long body": GOOD + "x" * 301,
        }
        for label, text in bad.items():
            self.assertTrue(self.p(text).errors, label)

    def test_file_name_is_checked(self):
        self.assertTrue(self.p(GOOD, "invite.md").errors)
        self.assertTrue(self.p(GOOD, "20261340-invite-bot.md").errors)

    def test_internal_changes_only_warn(self):
        f = self.p(GOOD.replace("Invite one bot by role", "Refactor the bot manager"))
        self.assertEqual(f.errors, [])
        self.assertTrue(f.warnings)


class Flow(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for n in ("agents-snippet.md", "fragments-readme.md", "sources.json"):
            shutil.copy(cl.HERE / n, self.tmp / n)
        self.saved = (cl.HERE, cl.ROOT, cl.RELEASES_DIR, cl.DISCORD_DIR, cl.SOURCES_FILE)
        cl.HERE, cl.ROOT = self.tmp, self.tmp
        cl.RELEASES_DIR, cl.DISCORD_DIR, cl.SOURCES_FILE = self.tmp / "releases", self.tmp / "discord", self.tmp / "sources.json"
        self.bots = self.tmp / "bots"
        self.manager = self.tmp / "manager"
        for d in (self.bots, self.manager):
            d.mkdir()

    def tearDown(self):
        cl.HERE, cl.ROOT, cl.RELEASES_DIR, cl.DISCORD_DIR, cl.SOURCES_FILE = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def frag(self, d, name, area, typ, aud, title, body=""):
        (d / name).write_text(f"---\narea: {area}\ntype: {typ}\naudience: {aud}\ntitle: {title}\n---\n{body}\n", encoding="utf-8")

    def args(self, **kw):
        base = dict(id="2026-10-03", date=None, server=None, manager=None, addon=None, renderer=None, remote=False,
                    source=[f"bots={self.bots}", f"manager={self.manager}"], dry_run=False)
        base.update(kw)
        return type("A", (), base)()

    def test_release_collects_once_and_renders_everything(self):
        self.frag(self.bots, "20261002-invite.md", "bots", "added", "players", "Invite one bot by role", "Pick a role.")
        self.frag(self.bots, "20261002-economy.md", "bots", "added", "admins", "Bot economy, off by default")
        self.frag(self.manager, "20261002-modules.md", "manager", "added", "admins", "Modules page with status badges")
        self.assertEqual(cl.cmd_release(self.args(server="0.261002.13", manager="0.4.0")), 0)
        rel = json.loads((self.tmp / "releases" / "2026-10-03.json").read_text(encoding="utf-8"))
        self.assertEqual(len(rel["entries"]), 3)
        md = (self.tmp / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## 2026-10-03 - Server 0.261002.13 · Manager 0.4.0", md)
        self.assertLess(md.index("For players"), md.index("For server owners"))
        self.assertIn("- Added: Invite one bot by role. Pick a role.", md)
        self.assertTrue((self.tmp / "discord" / "2026-10-03.txt").exists())
        self.assertTrue((self.tmp / "changelog.json").exists())
        # a second release only takes what is new
        self.assertEqual(cl.cmd_release(self.args(id="2026-10-04")), 1)
        self.frag(self.bots, "20261003-stock.md", "bots", "fixed", "players", "Stock tab shows each limit")
        self.assertEqual(cl.cmd_release(self.args(id="2026-10-04")), 0)
        rel2 = json.loads((self.tmp / "releases" / "2026-10-04.json").read_text(encoding="utf-8"))
        self.assertEqual([e["title"] for e in rel2["entries"]], ["Stock tab shows each limit"])
        md = (self.tmp / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertLess(md.index("## 2026-10-04"), md.index("## 2026-10-03"), "newest first")

    def test_an_invalid_fragment_blocks_the_release(self):
        (self.bots / "20261002-bad.md").write_text("no front matter", encoding="utf-8")
        self.assertEqual(cl.cmd_release(self.args()), 1)
        self.assertFalse((self.tmp / "releases").exists())

    def test_dry_run_writes_nothing(self):
        self.frag(self.bots, "20261002-invite.md", "bots", "added", "players", "Invite one bot by role")
        self.assertEqual(cl.cmd_release(self.args(dry_run=True)), 0)
        self.assertFalse((self.tmp / "releases").exists())

    def test_discord_messages_stay_under_the_limit_and_keep_bullets_whole(self):
        entries = [{"id": f"bots:2026100{i % 9 + 1}-x{i}.md", "source": "bots", "repo": "r", "date": "2026-10-03", "area": ["bots", "manager", "server"][i % 3],
                    "type": "added", "audience": "players", "title": f"Change number {i} that does something", "body": "word " * 40} for i in range(40)]
        msgs = cl.render_discord({"id": "2026-10-03", "versions": {"server": "1"}, "entries": entries})
        self.assertGreater(len(msgs), 1)
        self.assertTrue(all(len(m) <= cl.DISCORD_LIMIT for m in msgs))
        joined = "\n".join(msgs)
        for i in range(40):
            self.assertIn(f"Change number {i} that", joined)

    def test_sync_instructions_is_idempotent_and_keeps_existing_text(self):
        repo = self.tmp / "repo"
        repo.mkdir()
        (repo / "AGENTS.md").write_text("# AGENTS.md\n\nIntro line.\n\n## What this is\n\nText.\n", encoding="utf-8")
        cl.cmd_sync(type("A", (), {"paths": [str(repo)], "bottom": False})())
        first = (repo / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Intro line.", first)
        self.assertIn("## Changelog (shared by all CoA repositories)", first)
        self.assertLess(first.index("## Changelog"), first.index("## What this is"))
        self.assertEqual((repo / "CLAUDE.md").read_text(encoding="utf-8"), "@AGENTS.md\n")
        self.assertEqual((repo / "GEMINI.md").read_text(encoding="utf-8"), "@AGENTS.md\n")
        self.assertTrue((repo / "changelog.d" / "README.md").exists())
        cl.cmd_sync(type("A", (), {"paths": [str(repo)], "bottom": False})())
        self.assertEqual(first, (repo / "AGENTS.md").read_text(encoding="utf-8"))
        # an existing CLAUDE.md is left alone
        (repo / "CLAUDE.md").write_text("@AGENTS.md\nextra\n", encoding="utf-8")
        cl.cmd_sync(type("A", (), {"paths": [str(repo)], "bottom": False})())
        self.assertIn("extra", (repo / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_new_writes_a_valid_file(self):
        d = self.tmp / "out"
        a = type("A", (), dict(area="bots", type="fixed", audience="players", title="Stock tab shows each limit", body="Body.", date="2026-10-03", dir=str(d)))()
        self.assertEqual(cl.cmd_new(a), 0)
        files = list(d.glob("*.md"))
        self.assertEqual([f.name for f in files], ["20261003-stock-tab-shows-each-limit.md"])
        self.assertEqual(cl.parse_fragment("x", "x", files[0].name, files[0].read_text(encoding="utf-8")).errors, [])


if __name__ == "__main__":
    unittest.main()
