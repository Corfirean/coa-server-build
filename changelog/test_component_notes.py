import unittest
from component_notes import component_notes


class ComponentNotes(unittest.TestCase):
    def test_legacy_baseline_counts_upstream_without_inventing_versions(self):
        lock = {'components': {'core': {'repository': 'x/core', 'sha': 'c'},
                'upstream': {'repository': 'x/upstream', 'sha': 'u'},
                'squid': {'repository': 'x/squid', 'sha': 's', 'ref': 'v2.0'}}}
        def fetch(path):
            if '/compare/' in path:
                return {'ahead_by': 130, 'html_url': 'https://example.com/compare'}
            return {'html_url': 'https://example.com/release', 'body': 'Release notes'}
        notes = component_notes(lock, {'core': {'commit': 'old'}}, fetch)
        self.assertIn('130', notes[0]['title'])
        self.assertNotIn('→', notes[1]['title'])
        self.assertIn('not recorded', notes[1]['body'])

    def test_unchanged_revision_is_explicit(self):
        item = {'repository': 'x/scaling', 'sha': '123456789', 'ref': 'main'}
        notes = component_notes({'components': {'scaling': item}}, {'components': {'scaling': item}})
        self.assertIn('unchanged', notes[0]['title'])
