import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


spec = importlib.util.spec_from_file_location("external", Path(__file__).with_name("prepare-external-modules.py"))
external = importlib.util.module_from_spec(spec)
spec.loader.exec_module(external)


class ExternalModuleTests(unittest.TestCase):
    def test_pbc_package_leaves_the_default_connection_empty_for_legacy_upgrades(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = root / "module"
            files = {
                "prompts/enUS/CharacterContext.default.txt": "Default prompt",
                "frontend/dist/index.html": "<html></html>",
                "characters/Example.card.txt": "Example card",
                "connections/openai.jsonc.example": "{}",
                "conf/playerbots_characters.conf.dist": (
                    'PBC.Enable = 1\nPBC.DefaultConnection = "connections/openai.jsonc"\n'
                    'PBC.PromptsPath = "prompts"\nPBC.CharacterCardsPath = "characters"\n'
                    'PBC.HttpServerFrontendPath = "frontend/dist"\n'
                ),
                "LICENSE": "Fixture license",
            }
            for path, content in files.items():
                target = module / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            out = root / "out"
            subprocess.run([sys.executable, "-B", Path(__file__).with_name("package-mod-pbc.py"),
                            "--module", module, "--out", out], check=True)
            conf = (out / "Core/configs/modules/playerbots_characters.conf.dist").read_text(encoding="utf-8")
            self.assertIn('PBC.DefaultConnection = ""', conf.splitlines())
            self.assertIn("PBC.Enable = 0", conf.splitlines())

    def test_patches_are_pinned_idempotent_and_reject_unexpected_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = root / "pipeline"
            (pipeline / "patches").mkdir(parents=True)
            modules = {}
            for name, folder in external.MODULE_FOLDERS.items():
                target = root / "core/modules" / folder
                target.mkdir(parents=True)
                external.git(target, "init")
                external.git(target, "config", "core.autocrlf", "false")
                (target / "source.txt").write_bytes(b"original\n")
                (target / ".gitignore").write_bytes(b"*.sql\n")
                external.git(target, "add", "source.txt", ".gitignore")
                external.git(target, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                             "commit", "-m", "Fixture")
                sha = external.git(target, "rev-parse", "HEAD").decode().strip()
                created = target / "new.sql"
                if name == "mod-pbc":
                    created.write_bytes(b"SELECT 1;\n")
                    external.git(target, "add", "-f", "new.sql")
                else:
                    (target / "source.txt").write_bytes(b"patched\n")
                patch = external.git(target, "diff", "--binary", "--full-index", "HEAD", "--")
                external.git(target, "config", "core.abbrev", "20")
                if created.exists():
                    external.git(target, "rm", "-f", "new.sql")
                (target / "source.txt").write_bytes(b"original\n")
                filename = "patches/" + name + ".patch"
                (pipeline / filename).write_bytes(patch)
                modules[name] = dict(repository="test/fixture", sha=sha, patch=filename,
                                     patchSha256=hashlib.sha256(patch).hexdigest())
            metadata = pipeline / "external-modules.json"
            metadata.write_text(json.dumps(dict(schema=1, modules=modules)))
            previous = external.PIPELINE
            external.PIPELINE = pipeline
            try:
                external.prepare(root / "core")
                external.prepare(root / "core")
                target = root / "core/modules/mod-playerbots/source.txt"
                self.assertEqual(target.read_bytes(), b"patched\n")
                self.assertEqual((root / "core/modules/mod-pbc/new.sql").read_bytes(), b"SELECT 1;\n")
                target.write_bytes(b"unexpected\n")
                with self.assertRaisesRegex(RuntimeError, "unexpected changes"):
                    external.prepare(root / "core")
                (pipeline / modules["squid"]["patch"]).write_bytes(b"damaged")
                with self.assertRaisesRegex(RuntimeError, "checksum differs"):
                    external.definition()
            finally:
                external.PIPELINE = previous
