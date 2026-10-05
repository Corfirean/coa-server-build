import json
from pathlib import Path
import tempfile
import unittest
import os
import subprocess
import sys
from squid_playerbots import validate_bots, prepare_playerbots


class IntegrationTests(unittest.TestCase):
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
            (base / "bot.sql").write_text("DROP TABLE IF EXISTS bot; CREATE TABLE bot(id INT);")
            updates = base.parent / "updates"
            updates.mkdir()
            migration = updates / "applied.sql"
            migration.write_bytes(b"DELETE FROM bot;\r\n")
            calls = []
            def mysql(sql):
                calls.append(sql)
                if "SELECT TABLE_NAME" in sql:
                    return "bot\nupdates"
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
                    return "another_table\nupdates"
                return mysql(sql)
            with self.assertRaisesRegex(RuntimeError, "missing a base table"):
                prepare_playerbots(root, {"mysqlPort": 3307}, incomplete)
            self.assertFalse(any("DROP TABLE" in call for call in calls))
            migration.write_text("DELETE FROM bot WHERE id=1;")
            def mismatched(sql):
                if "SELECT name,hash" in sql:
                    return "applied.sql\t" + "0" * 40
                return mysql(sql)
            with self.assertRaisesRegex(RuntimeError, "history does not match"):
                prepare_playerbots(root, {"mysqlPort": 3307}, mismatched)



if __name__ == "__main__":
    unittest.main()
