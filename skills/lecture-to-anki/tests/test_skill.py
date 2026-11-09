import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import plan_update
import export_anki
from prepare_media import render_pdf, extract_pptx_image


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'Course'
        (self.root / 'Lectures').mkdir(parents=True)
        (self.root / 'Exams').mkdir()
        self.out = self.root / 'anki-output'
        self.out.mkdir()
        self.lecture = self.root / 'Lectures' / 'L01.md'
        self.lecture.write_text('Dijkstra requires nonnegative edge weights.', encoding='utf-8')

    def make_cards(self, with_media=False):
        question = 'Which weights are allowed in Dijkstra?'
        media = []
        if with_media:
            question = '<img src="figure.png"> What is the marked node?'
            media = ['media/figure.png']
        payload = {
            'deck': 'Algorithms',
            'cards': [
                {'id': 'graphs.dijkstra.assumption', 'type': 'basic', 'kind': 'assumption',
                 'front': question, 'back': 'Nonnegative weights.',
                 'source_file': 'Lectures/L01.md', 'source_location': 'paragraph 1',
                 'tags': ['topic::graphs', 'priority::high'], 'media': media},
                {'id': 'graphs.bfs.complexity', 'type': 'cloze', 'kind': 'complexity',
                 'text': 'BFS uses {{c1::\\(O(n+m)\\)}} time with adjacency lists.',
                 'extra': 'All vertices and edges scanned a constant number of times.',
                 'source_file': 'Lectures/L01.md', 'source_location': 'paragraph 1',
                 'tags': ['topic::graphs']}
            ]}
        path = self.out / 'cards.json'
        path.write_text(json.dumps(payload), encoding='utf-8')
        return path

    def test_extract_and_update_new_changed_deleted(self):
        p = subprocess.run([sys.executable, str(SCRIPTS / 'extract_sources.py'), str(self.root)],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        reports = json.loads((self.out / 'sources_report.json').read_text())
        self.assertEqual(reports['files_found'], 1)
        self.assertRegex(reports['files'][0]['sha256'], '^[0-9a-f]{64}$')
        self.make_cards()
        export_anki.export(self.out / 'cards.json', self.out, 'text', self.root)
        before = plan_update.plan(self.root, self.out / 'source_manifest.json', self.out / 'cards.json')
        self.assertEqual(before['summary']['changed'], 0)
        self.assertEqual(before['summary']['new'], 0)
        self.lecture.write_text('Dijkstra requires nonnegative weights, 2026 update.')
        (self.root / 'Exams' / 'Exam25.md').write_text('Exam topic')
        after = plan_update.plan(self.root, self.out / 'source_manifest.json', self.out / 'cards.json')
        self.assertEqual(after['changed'], ['Lectures/L01.md'])
        self.assertEqual(after['new'], ['Exams/Exam25.md'])
        self.assertEqual(len(after['affected_cards']), 2)
        self.lecture.unlink()
        deleted = plan_update.plan(self.root, self.out / 'source_manifest.json', self.out / 'cards.json')
        self.assertEqual(deleted['deleted'], ['Lectures/L01.md'])
        self.assertEqual(len(deleted['affected_cards']), 2)

    def test_export_text_math_and_tags(self):
        src = self.make_cards()
        report = export_anki.export(src, self.out, 'text', self.root)
        self.assertEqual(report['exported_notes'], 2)
        self.assertEqual(report['cloze_cards'], 1)
        self.assertEqual(report['notes_without_explicit_ids'], 0)
        self.assertIn('kind::assumption', (self.out / 'basic.txt').read_text())
        self.assertIn('{{c1::\\(O(n+m)\\)}}', (self.out / 'cloze.txt').read_text())
        self.assertTrue((self.out / 'source_manifest.json').exists())

    def test_update_preserves_ids_on_question_changes(self):
        src = self.make_cards()
        original = json.loads(src.read_text())
        old_id = original['cards'][0]['id']
        original['cards'][0]['front'] = 'Under what weight assumption is Dijkstra correct?'
        src.write_text(json.dumps(original))
        deck, notes, *_ = export_anki.normalize_and_validate(src, self.out)
        self.assertEqual(notes[0]['id'], old_id)
        self.assertEqual(export_anki.stable_number('deck', deck),
                         export_anki.stable_number('deck', deck))

    def test_validation_rejects_media_escaping_and_broken_references(self):
        src = self.make_cards(True)
        with self.assertRaisesRegex(ValueError, 'missing media'):
            export_anki.normalize_and_validate(src, self.out)
        (self.out / 'media').mkdir()
        (self.out / 'media' / 'figure.png').write_bytes(b'png')
        _, cards, media, *_ = export_anki.normalize_and_validate(src, self.out)
        self.assertEqual(len(media), 1)
        self.assertEqual(cards[0]['media'], ['media/figure.png'])
        payload = json.loads(src.read_text())
        payload['cards'][0]['media'] = ['../../etc/passwd']
        src.write_text(json.dumps(payload))
        with self.assertRaisesRegex(ValueError, 'escapes output directory'):
            export_anki.normalize_and_validate(src, self.out)

    def test_duplicate_id_error(self):
        src = self.make_cards()
        payload = json.loads(src.read_text())
        payload['cards'][1]['id'] = payload['cards'][0]['id']
        src.write_text(json.dumps(payload))
        with self.assertRaisesRegex(ValueError, 'duplicate id'):
            export_anki.normalize_and_validate(src, self.out)

    def test_render_pdf_crop(self):
        try:
            import fitz
        except ImportError:
            self.skipTest('pymupdf unavailable')
        document = fitz.open()
        page = document.new_page(width=420, height=320)
        page.draw_rect(fitz.Rect(40, 40, 160, 130))
        page.insert_text((80, 90), 'G')
        path = self.root / 'Lectures' / 'L02.pdf'
        document.save(str(path))
        document.close()
        img = render_pdf(path, 1, '30,30,180,150', 145, self.out / 'media')
        self.assertTrue(img.read_bytes().startswith(b'\x89PNG'))
        self.assertEqual(img, render_pdf(path, 1, '30,30,180,150', 145, self.out / 'media'))

    def test_pptx_picture_extract(self):
        path = self.root / 'Lectures' / 'L03.pptx'
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr('ppt/slides/slide1.xml', '<p:sld xmlns:p="a" xmlns:a="b" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><a:blip r:embed="rId1"/></p:sld>')
            zf.writestr('ppt/slides/_rels/slide1.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/></Relationships>')
            zf.writestr('ppt/media/image1.png', b'\x89PNG\r\n\x1a\n' + b'content')
        img = extract_pptx_image(path, 1, 1, self.out / 'media')
        self.assertTrue(img.name.startswith('lta_L03_slide1_image1_'))
        self.assertEqual(img.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')

    def test_optional_genanki_export(self):
        try:
            import genanki
        except ImportError:
            self.skipTest('genanki not installed (optional)')
        self.make_cards()
        report = export_anki.export(self.out / 'cards.json', self.out, 'both', self.root)
        self.assertTrue(Path(report['files']['apkg']).is_file())
        with zipfile.ZipFile(report['files']['apkg']) as zf:
            self.assertIn('collection.anki2', zf.namelist())
            self.assertIn('media', zf.namelist())


if __name__ == '__main__':
    unittest.main()
