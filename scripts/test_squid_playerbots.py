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

    def test_provisioning_is_idempotent_and_changed_sql_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            modules = root / "Core/configs/modules"
            modules.mkdir(parents=True)
            (modules / "playerbots.conf").write_text("AiPlayerbot.Enabled = 0\n")
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


if __name__ == "__main__":
    unittest.main()
