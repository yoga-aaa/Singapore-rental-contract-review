import json
import tempfile
import unittest
from pathlib import Path
from scripts.bootstrap import HASHES
from scripts.restore_private_references import restore_bundle

ROOT = Path(__file__).resolve().parents[1]


class ReferenceRestorationTests(unittest.TestCase):
    def manifest(self, root, entries):
        (root / 'manifest.json').write_text(json.dumps({'artifacts': entries}), encoding='utf-8')

    def test_unregistered_pdf_path_is_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.manifest(root, [{'path': '../escape.pdf', 'sha256': 'bad'}])
            with self.assertRaisesRegex(ValueError, 'registered'):
                restore_bundle(root, root)
            self.assertFalse((root / 'snapshot').exists())

    def test_changed_frozen_hash_is_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            entries = [{'path': 'snapshot/data/source_documents/' + name, 'sha256': sha}
                       for name, sha in HASHES.items()]
            entries[0]['sha256'] = '0' * 64
            self.manifest(root, entries)
            with self.assertRaisesRegex(ValueError, 'hash'):
                restore_bundle(root, root)
            self.assertFalse((root / 'snapshot').exists())

    @unittest.skipUnless(all((ROOT / 'data/source_documents' / name).exists() for name in HASHES),
                         'Run bootstrap for fixed official PDF fixtures')
    def test_verified_restoration_is_idempotent_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            entries = [{'path': 'snapshot/data/source_documents/' + name, 'sha256': sha}
                       for name, sha in HASHES.items()]
            self.manifest(root, entries)
            result = restore_bundle(root, ROOT / 'data/source_documents')
            self.assertEqual(result, {'restored': 2, 'already_verified': 0, 'model_api_calls': 0})
            self.assertEqual(restore_bundle(root, ROOT / 'data/source_documents')['restored'], 0)
            target = root / entries[0]['path']
            target.write_bytes(b'changed fixture')
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                restore_bundle(root, ROOT / 'data/source_documents')
            self.assertEqual(target.read_bytes(), b'changed fixture')
