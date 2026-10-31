import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


spec = importlib.util.spec_from_file_location("external", Path(__file__).with_name("prepare-external-modules.py"))
external = importlib.util.module_from_spec(spec)
spec.loader.exec_module(external)


class ExternalModuleTests(unittest.TestCase):
    def test_patches_are_pinned_idempotent_and_reject_unexpected_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = root / "pipeline"
            (pipeline / "patches").mkdir(parents=True)
            modules = {}
            for name, folder in (("squid", "mod-playerbots"), ("dungeon-clear", "mod-dungeon-clear")):
                target = root / "core/modules" / folder
                target.mkdir(parents=True)
                external.git(target, "init")
                external.git(target, "config", "core.autocrlf", "false")
                (target / "source.txt").write_bytes(b"original\n")
                external.git(target, "add", "source.txt")
                external.git(target, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                             "commit", "-m", "Fixture")
                sha = external.git(target, "rev-parse", "HEAD").decode().strip()
                (target / "source.txt").write_bytes(b"patched\n")
                patch = external.git(target, "diff", "--binary", "HEAD", "--")
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
                target.write_bytes(b"unexpected\n")
                with self.assertRaisesRegex(RuntimeError, "unexpected changes"):
                    external.prepare(root / "core")
                (pipeline / modules["squid"]["patch"]).write_bytes(b"damaged")
                with self.assertRaisesRegex(RuntimeError, "checksum differs"):
                    external.definition()
            finally:
                external.PIPELINE = previous
