import hashlib
import io
import subprocess
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('sources', Path(__file__).with_name('upgrade-sources.py'))
sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sources)


class SourceTests(unittest.TestCase):
    def test_resolver_retains_all_published_sources_and_freezes_legacy_tags(self):
        releases = [{'tag_name': tag, 'draft': False} for tag in
                    ['server-0.261015.58', 'server-0.261013.54', 'server-0.261005.0', 'edge', 'stable']]
        versions = {'base': '0.2.0', 'server-0.261015.58': '0.261015.58',
                    'server-0.261013.54': '0.261013.54', 'server-0.261005.0': '0.261005.0',
                    'edge': '0.261010.33', 'stable': '0.261010.32'}
        def api(path):
            return releases if 'releases?' in path else {'tag_name': path.rsplit('/', 1)[-1]}
        def source(release, role):
            version = versions[release['tag_name']]
            return {'role': role, 'tag': release['tag_name'], 'version': version,
                    'manifestSha256': hashlib.sha256(version.encode()).hexdigest()}
        pointer = ({'payload': 'signed'}, {'releaseTag': 'server-0.261015.58'})
        with patch.object(sources, 'api', side_effect=api), patch.object(sources, 'source', side_effect=source), \
             patch.object(sources, 'channel', return_value=pointer):
            result = sources.resolve()
        self.assertEqual({s['version'] for s in result}, set(versions.values()))
        self.assertEqual([s['role'] for s in result], ['base'] + [f'stable-{i}' for i in range(1, 6)])
        self.assertEqual(result[1]['channelPointer'], pointer[0])

    def test_duplicate_version_with_different_signed_bytes_is_rejected(self):
        def source(release, role):
            return {'role': role, 'version': '0.2.0' if release['tag_name'] == 'base' else '0.261015.58',
                    'manifestSha256': hashlib.sha256(release['tag_name'].encode()).hexdigest()}
        def api(path):
            return [{'tag_name': 'stable', 'draft': False}] if 'releases?' in path else {'tag_name': path.rsplit('/', 1)[-1]}
        with patch.object(sources, 'api', side_effect=api), patch.object(sources, 'source', side_effect=source), \
             patch.object(sources, 'channel', return_value=({}, {'releaseTag': 'server-0.261015.58'})):
            with self.assertRaisesRegex(RuntimeError, 'Different signed packages'):
                sources.resolve()

    def test_every_frozen_source_is_downloaded_and_invalid_paths_are_rejected(self):
        lock = self.lock()
        extra = dict(lock['upgradeSources'][-1], role='stable-3')
        lock['upgradeSources'].append(extra)
        with tempfile.TemporaryDirectory() as directory, patch.object(sources, 'fetch', return_value=b'original'):
            sources.download(lock, Path(directory))
            self.assertEqual((Path(directory) / 'stable-3/manifest.json').read_bytes(), b'original')
        extra['role'] = '../outside'
        with patch.object(sources, 'fetch') as fetch:
            with self.assertRaises(RuntimeError):
                sources.download(lock, Path('unused'))
            fetch.assert_not_called()

    def test_matrix_downloads_only_base_and_selected_stable(self):
        lock = self.lock()
        with tempfile.TemporaryDirectory() as directory, patch.object(sources, 'fetch', return_value=b'original') as fetch:
            folder = Path(directory)
            sources.download(lock, folder, ['base', 'stable-2'])
            self.assertEqual(fetch.call_count, 4)
            self.assertTrue((folder / 'base/manifest.json').exists())
            self.assertTrue((folder / 'stable-2/manifest.json').exists())
            self.assertFalse((folder / 'stable-1').exists())
        self.assertEqual([s['role'] for s in sources.selected_sources(lock, ['base', 'base'])], ['base'])
        with self.assertRaises(RuntimeError):
            sources.selected_sources(lock, ['../outside'])

    def lock(self):
        return {'upgradeSources': [{'role': role, 'assets': {name: {
            'url': 'https://github.com/Corfirean/coa-server-build/releases/download/stable/' + name,
            'sha256': hashlib.sha256(b'original').hexdigest()}
            for name in ('manifest.json', 'manifest.json.sig')}} for role in sources.ROLES]}

    def test_overwritten_legacy_asset_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(sources, 'fetch', return_value=b'changed'):
            with self.assertRaises(RuntimeError):
                sources.download(self.lock(), Path(directory))
            self.assertFalse((Path(directory) / 'base/manifest.json').exists())

    def test_invalid_roles_are_rejected_before_network_or_writes(self):
        lock = self.lock()
        lock['upgradeSources'][0]['role'] = '../outside'
        with tempfile.TemporaryDirectory() as directory, patch.object(sources, 'fetch') as fetch:
            with self.assertRaises(RuntimeError):
                sources.download(lock, Path(directory))
            fetch.assert_not_called()

    def test_network_failure_is_not_a_legacy_fallback(self):
        result = type('Result', (), {'returncode': 1, 'stdout': '{"status":"500"}'})()
        with patch.object(sources.subprocess, 'run', return_value=result):
            with self.assertRaises(RuntimeError):
                sources.channel()

    def test_archive_hash_and_size_are_required_before_installing_the_download(self):
        url = 'https://github.com/Corfirean/coa-server-build/releases/download/stable/server.tar.zst.001'
        for raw in (b'short', b'wrong!', b'too-long'):
            with tempfile.TemporaryDirectory() as directory, patch.object(sources.urllib.request, 'urlopen', return_value=io.BytesIO(raw)):
                target = Path(directory) / 'server.tar.zst.001'
                with self.assertRaises(RuntimeError):
                    sources.download_part(url, target, 6, hashlib.sha256(b'correct').hexdigest())
                self.assertFalse(target.exists())
                self.assertFalse(target.with_name(target.name + '.partial').exists())

    def test_valid_archive_is_reused_only_after_verification(self):
        url = 'https://github.com/Corfirean/coa-server-build/releases/download/stable/part'
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'part'
            with patch.object(sources.urllib.request, 'urlopen', return_value=io.BytesIO(b'good')):
                sources.download_part(url, target, 4, hashlib.sha256(b'good').hexdigest())
            with patch.object(sources.urllib.request, 'urlopen') as fetch:
                sources.download_part(url, target, 4, hashlib.sha256(b'good').hexdigest())
                fetch.assert_not_called()
            target.write_bytes(b'bad!')
            with self.assertRaises(RuntimeError):
                sources.download_part(url, target, 4, hashlib.sha256(b'good').hexdigest())

    def test_an_existing_partial_download_is_not_deleted(self):
        url = 'https://github.com/Corfirean/coa-server-build/releases/download/stable/part'
        with tempfile.TemporaryDirectory() as directory, patch.object(sources.urllib.request, 'urlopen', return_value=io.BytesIO(b'good')):
            target = Path(directory) / 'part'
            partial = Path(directory) / 'part.partial'
            partial.write_bytes(b'other download')
            with self.assertRaises(FileExistsError):
                sources.download_part(url, target, 4, hashlib.sha256(b'good').hexdigest())
            self.assertEqual(partial.read_bytes(), b'other download')

    def test_invalid_signature_stops_before_archive_download(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(sources, 'download'), \
             patch.object(sources.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'verify-manifest')), \
             patch.object(sources, 'download_part') as fetch:
            with self.assertRaises(subprocess.CalledProcessError):
                sources.download_packages(self.lock(), Path(directory), Path('tool'))
            fetch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
