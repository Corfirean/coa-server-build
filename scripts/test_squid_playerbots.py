import json
from pathlib import Path
import tempfile
import unittest
import os
import subprocess
import sys
import runpy
from types import SimpleNamespace
from unittest.mock import patch
from squid_playerbots import validate_bots, prepare_playerbots


class IntegrationTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "The repack launcher requires Windows")
    def test_squid_world_can_become_ready_after_the_normal_startup_deadline(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            modules = root / "Core/configs/modules"
            modules.mkdir(parents=True)
            (modules / "mod_coa_playerbots.conf").write_text("CoaBots.Enable = 0\n")
            for enabled in (False, True):
                (modules / "playerbots.conf").write_text("AiPlayerbot.Enabled = " + str(int(enabled)) + "\n")
                launcher = runpy.run_path(str(Path(__file__).with_name("manage.py")))
                state = {"time": 0, "spawned": False}
                def sleep(seconds):
                    state["time"] += seconds
                def spawn(*args):
                    state["spawned"] = True
                launcher["start_world"].__globals__.update(
                    ROOT=root, STATE=root / ".state", start_mysql=lambda config: None,
                    ensure_free=lambda port: None, wait_relay=lambda: None, spawn=spawn,
                    process=lambda name: state["spawned"] if name in ("world", "supervisor") else None,
                    ready=lambda name, port: state["time"] >= 200,
                    time=SimpleNamespace(monotonic=lambda: state["time"], sleep=sleep))
                with patch("squid_playerbots.prepare_playerbots"):
                    if enabled:
                        launcher["start_world"]({"worldPort": 1, "raPort": 2}, 0)
                        self.assertEqual(state["time"], 200)
                    else:
                        with self.assertRaisesRegex(RuntimeError, "still starting"):
                            launcher["start_world"]({"worldPort": 1, "raPort": 2}, 0)

    @unittest.skipUnless(os.name == "nt", "The repack launcher requires Windows")
    def test_large_import_does_not_use_the_normal_database_command_deadline(self):
        launcher = runpy.run_path(str(Path(__file__).with_name("manage.py")))
        with patch("subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=b"")) as execute:
            launcher["mysql"]("SELECT 1;")
            self.assertEqual(execute.call_args.kwargs["timeout"], 90)
            launcher["mysql"]("x" * (1024 * 1024 + 1))
            self.assertEqual(execute.call_args.kwargs["timeout"], 900)
            launcher["mysql"](admin="ping")
            self.assertEqual(execute.call_args.kwargs["timeout"], 90)

    @unittest.skipUnless(os.name == "nt", "The repack launcher requires Windows")
    def test_primary_launcher_loads_its_helper_in_isolated_python(self):
        launcher = Path(os.environ.get('COA_LAUNCHER_TEST_SCRIPT', Path(__file__).with_name('manage.py')))
        code = "import runpy,sys;from pathlib import Path;runpy.run_path(sys.argv[1]);import squid_playerbots;assert Path(squid_playerbots.__file__).parent == Path(sys.argv[1]).parent"
        result = subprocess.run([sys.executable, '-I', '-c', code, str(launcher)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_manual_conflict_and_missing_or_invalid_key(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            modules = root / "Core/configs/modules"
            modules.mkdir(parents=True)
            (modules / "mod_coa_playerbots.conf").write_text("CoaBots.Enable = 1\n")
            squid = modules / "playerbots.conf"
            for value in ("1", "true", "2", "invalid"):
                squid.write_text("AiPlayerbot.Enabled = " + value + "\n")
                with self.assertRaises(RuntimeError):
                    validate_bots(root)
            squid.write_text("# omitted key\n")
            with self.assertRaises(RuntimeError):
                validate_bots(root)
            squid.write_text("AiPlayerbot.Enabled = 0\n")
            validate_bots(root)

    def test_disabled_bots_do_not_touch_sql_or_require_packaged_sql(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            modules = root / "Core/configs/modules"
            modules.mkdir(parents=True)
            (modules / "playerbots.conf").write_text("AiPlayerbot.Enabled = 0\n")
            def forbidden(sql):
                self.fail("Disabled module accessed SQL")
            prepare_playerbots(root, {"mysqlPort": 3307}, forbidden)

    def test_provisioning_is_idempotent_and_changed_sql_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            modules = root / "Core/configs/modules"
            modules.mkdir(parents=True)
            (modules / "playerbots.conf").write_text("AiPlayerbot.Enabled = 1\n")
            (root / "Settings").mkdir()
            (root / "Settings/database.json").write_text(json.dumps({"appPassword": "a" * 48}))
            (root / "Core/configs/worldserver.conf").write_text('WorldDatabaseInfo = "x;x;x;x;acore_world"\nCharacterDatabaseInfo = "x;x;x;x;acore_characters"\n')
            base = root / "Extras/SquidPlayerbots/sql/playerbots/base"
            base.mkdir(parents=True)
            source = base / "bot.sql"
            source.write_text("CREATE TABLE bot(id INT);")
            calls, ledger = [], {}
            def mysql(text):
                calls.append(text)
                if "SELECT TABLE_NAME" in text and "TABLE_SCHEMA='acore_playerbots'" in text:
                    return "bot\ncoa_squid_migrations" if ledger else ""
                if text.startswith("SELECT path,sha256 FROM `acore_playerbots`"):
                    return "\n".join(name + "\t" + digest for name, digest in ledger.items())
                if "coa_squid_migrations VALUES" in text:
                    import re
                    name, digest = re.search(r"VALUES \('([^']+)','([^']+)'\)", text).groups()
                    ledger[name] = digest
                return ""
            prepare_playerbots(root, {"mysqlPort": 3307}, mysql)
            prepare_playerbots(root, {"mysqlPort": 3307}, mysql)
            self.assertEqual(sum("CREATE TABLE bot(" in call for call in calls), 1)
            self.assertIn(";3307;acore;", (modules / "playerbots.conf").read_text())
            source.write_text("DROP TABLE bot;")
            with self.assertRaises(RuntimeError):
                prepare_playerbots(root, {"mysqlPort": 3307}, mysql)

    def test_imported_database_seeds_history_without_replaying_destructive_sql(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            modules = root / "Core/configs/modules"
            modules.mkdir(parents=True)
            (modules / "playerbots.conf").write_text("AiPlayerbot.Enabled = 1\n")
            (root / "Settings").mkdir()
            (root / "Settings/database.json").write_text(json.dumps({"appPassword": "a" * 48}))
            (root / "Core/configs/worldserver.conf").write_text('WorldDatabaseInfo = "x;x;x;x;acore_world"\nCharacterDatabaseInfo = "x;x;x;x;acore_characters"\n')
            base = root / "Extras/SquidPlayerbots/sql/playerbots/base"
            base.mkdir(parents=True)
            (base / "bot.sql").write_text("DROP TABLE IF EXISTS bot; CREATE TABLE bot(id INT); CREATE TABLE bot_cache(id INT);")
            updates = base.parent / "updates"
            updates.mkdir()
            migration = updates / "applied.sql"
            migration.write_bytes(b"DELETE FROM bot;\r\n")
            calls = []
            def mysql(sql):
                calls.append(sql)
                if "SELECT TABLE_NAME" in sql:
                    return "bot\nbot_cache\nupdates"
                if "SELECT COUNT(*)" in sql:
                    return "1" if "TABLE_SCHEMA='acore_playerbots'" in sql else "0"
                if "SELECT name,hash FROM `acore_playerbots`" in sql:
                    return "applied.sql\t" + hashlib.sha1(migration.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                return ""
            prepare_playerbots(root, {"mysqlPort": 3307}, mysql)
            self.assertFalse(any("DROP TABLE" in call or "DELETE FROM bot" in call for call in calls))
            self.assertTrue(any("playerbots/base/bot.sql" in call for call in calls))
            self.assertTrue(any("playerbots/updates/applied.sql" in call for call in calls))
            def incomplete(sql):
                if "SELECT TABLE_NAME" in sql:
                    return "bot\nupdates"
                return mysql(sql)
            with self.assertRaisesRegex(RuntimeError, "only some of its tables"):
                prepare_playerbots(root, {"mysqlPort": 3307}, incomplete)
            self.assertFalse(any("DROP TABLE" in call for call in calls))
            migration.write_text("DELETE FROM bot WHERE id=1;")
            def mismatched(sql):
                if "SELECT name,hash" in sql:
                    return "applied.sql\t" + "0" * 40
                return mysql(sql)
            with self.assertRaisesRegex(RuntimeError, "history does not match"):
                prepare_playerbots(root, {"mysqlPort": 3307}, mismatched)

    def test_interrupted_base_import_stays_pending_and_blocks_adoption_on_restart(self):
        for kind in ("playerbots", "world", "characters"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                sql_root = self.make_enabled_root(root)
                base = sql_root / kind / "base"
                base.mkdir(parents=True, exist_ok=True)
                (base / "large.sql").write_text("CREATE TABLE imported_data(id INT); INSERT INTO imported_data VALUES (1);")
                pending, created, calls = [], set(), []
                def mysql(sql):
                    calls.append(sql)
                    if "SELECT TABLE_NAME" in sql and f"TABLE_SCHEMA='acore_{kind}'" in sql:
                        return "\n".join(created)
                    if sql.startswith(f"SELECT path FROM `acore_{kind}`.coa_squid_pending"):
                        return "\n".join(pending)
                    if sql.startswith(f"CREATE TABLE IF NOT EXISTS `acore_{kind}`.coa_squid_pending"):
                        created.add("coa_squid_pending")
                    if sql.startswith(f"INSERT INTO `acore_{kind}`.coa_squid_pending"):
                        pending.append(kind + "/base/large.sql")
                    if "CREATE TABLE imported_data" in sql:
                        self.assertTrue(pending, "The marker must commit before the base SQL starts")
                        created.add("imported_data")
                        raise TimeoutError("base SQL exceeded 90 seconds")
                    return ""
                with self.assertRaises(TimeoutError):
                    prepare_playerbots(root, {"mysqlPort": 3307}, mysql)
                calls.clear()
                with self.assertRaisesRegex(RuntimeError, "base import was interrupted"):
                    prepare_playerbots(root, {"mysqlPort": 3307}, mysql)
                self.assertTrue(all(call.startswith("SELECT") for call in calls))
                self.assertEqual(pending, [kind + "/base/large.sql"])

    def test_successful_base_import_clears_pending_only_after_sql_and_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sql_root = self.make_enabled_root(root)
            (sql_root / "playerbots/base/done.sql").write_text("CREATE TABLE finished_data(id INT);")
            calls = []
            def mysql(sql):
                calls.append(sql)
                return ""
            prepare_playerbots(root, {"mysqlPort": 3307}, mysql)
            marker = next(i for i, call in enumerate(calls) if call.startswith("INSERT INTO `acore_playerbots`.coa_squid_pending"))
            imported = next(i for i, call in enumerate(calls) if "CREATE TABLE finished_data" in call)
            self.assertLess(marker, imported)
            statement = calls[imported]
            self.assertLess(statement.index("CREATE TABLE finished_data"), statement.index("coa_squid_migrations VALUES"))
            self.assertLess(statement.index("coa_squid_migrations VALUES"), statement.index("DELETE FROM `acore_playerbots`.coa_squid_pending"))

    def make_enabled_root(self, root):
        modules = root / "Core/configs/modules"
        modules.mkdir(parents=True)
        (modules / "playerbots.conf").write_text("AiPlayerbot.Enabled = 1\n")
        (root / "Settings").mkdir()
        (root / "Settings/database.json").write_text(json.dumps({"appPassword": "a" * 48}))
        (root / "Core/configs/worldserver.conf").write_text('WorldDatabaseInfo = "x;x;x;x;acore_world"\nCharacterDatabaseInfo = "x;x;x;x;acore_characters"\n')
        base = root / "Extras/SquidPlayerbots/sql/playerbots/base"
        base.mkdir(parents=True)
        return base.parent.parent

    def test_installer_ledger_normalizes_escaped_paths_and_skips_all_databases(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sql_root = self.make_enabled_root(root)
            for kind in ("playerbots", "world", "characters"):
                update = sql_root / kind / "updates"
                update.mkdir(parents=True)
                (update / "applied.sql").write_text("TRUNCATE TABLE precious_data;")
            calls = []
            def mysql(sql):
                calls.append(sql)
                if "SELECT TABLE_NAME" in sql and "TABLE_SCHEMA='acore_playerbots'" in sql:
                    return "bot\nupdates\ncoa_bots_installed"
                if "SELECT file FROM" in sql:
                    return "\n".join(kind + r"\\updates\\applied.sql" for kind in ("playerbots", "world", "characters")) + "\ncomplete"
                return ""
            prepare_playerbots(root, {"mysqlPort": 3307}, mysql)
            self.assertFalse(any("TRUNCATE" in call for call in calls))
            self.assertEqual(sum("coa_squid_migrations VALUES" in call for call in calls), 3)

    def test_existing_data_without_any_ledger_stops_before_mutations(self):
        for installer in (False, True):
            with self.subTest(installer=installer), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                self.make_enabled_root(root)
                calls = []
                def mysql(sql):
                    calls.append(sql)
                    if "SELECT TABLE_NAME" in sql and "TABLE_SCHEMA='acore_playerbots'" in sql:
                        return "bot\nupdates" + ("\ncoa_bots_installed" if installer else "")
                    if "SELECT file FROM" in sql:
                        return "complete"
                    if "SELECT EXISTS" in sql:
                        return "1"
                    return ""
                with self.assertRaisesRegex(RuntimeError, "Repair the imported database history"):
                    prepare_playerbots(root, {"mysqlPort": 3307}, mysql)
                self.assertTrue(all(call.startswith("SELECT") for call in calls))

    def test_base_adoption_is_per_file_for_each_database(self):
        for kind in ("playerbots", "world", "characters"):
            for present in (set(), {"first", "second"}, {"first"}):
                with self.subTest(kind=kind, present=present), tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    sql_root = self.make_enabled_root(root)
                    base = sql_root / kind / "base"
                    base.mkdir(parents=True, exist_ok=True)
                    (base / "tables.sql").write_text("DROP TABLE IF EXISTS first; CREATE TABLE first(id INT); DROP TABLE IF EXISTS second; CREATE TABLE second(id INT);")
                    calls = []
                    def mysql(sql):
                        calls.append(sql)
                        if "SELECT TABLE_NAME" in sql and f"TABLE_SCHEMA='acore_{kind}'" in sql:
                            return "\n".join(present | {"unrelated_existing_table"})
                        return ""
                    if len(present) == 1:
                        with self.assertRaisesRegex(RuntimeError, "only some of its tables"):
                            prepare_playerbots(root, {"mysqlPort": 3307}, mysql)
                    else:
                        prepare_playerbots(root, {"mysqlPort": 3307}, mysql)
                    self.assertEqual(any("DROP TABLE" in call for call in calls), not present)




if __name__ == "__main__":
    unittest.main()
