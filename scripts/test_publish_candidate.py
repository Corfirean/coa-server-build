import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from subprocess import CompletedProcess

spec = importlib.util.spec_from_file_location("publish", Path(__file__).with_name("publish-candidate.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PublicationTests(unittest.TestCase):
    def test_published_release_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "manifest.json").write_text(json.dumps({"version": "0.261010.40"}))
            with patch.object(module, "run") as run, patch.object(module.subprocess, "run", return_value=CompletedProcess([], 0, '{"isDraft":false}', '')):
                with self.assertRaisesRegex(RuntimeError, "already exists"):
                    module.publish(root, "owner/repo", "tool")
                self.assertEqual(run.call_count, 1)

    def test_hashes_detect_incomplete_or_changed_package(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            left, right = Path(a), Path(b)
            (left / 'part').write_bytes(b'original')
            self.assertNotEqual(module.hashes(left), module.hashes(right))
            (right / 'part').write_bytes(b'changed!')
            self.assertNotEqual(module.hashes(left), module.hashes(right))
            (right / 'part').write_bytes(b'original')
            self.assertEqual(module.hashes(left), module.hashes(right))


if __name__ == '__main__':
    unittest.main()
