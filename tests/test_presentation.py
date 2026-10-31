"""Offline regression checks for the real empty state and synthetic future episodes."""
import json
import tempfile
import unittest
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET
from scripts import build_site
from scripts.site_presentation import render_page


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.elements = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def tags(self, tag):
        return [a for t, a in self.elements if t == tag]


def sample(number=1):
    day = date(2026, 10, number)
    name = f'{day}-morning.mp3'
    return ({'date': str(day), 'edition': 'morning',
             'title': 'Synthetic renderer test, never published',
             'summary': 'A fictional fixture for testing the future episode display.',
             'sources': ['https://example.org/report?a=1&b=2'],
             'filename': name, 'public_only': True, 'privacy_reviewed': True}, Path(name), day)


class PresentationTests(unittest.TestCase):
    def test_empty_state_has_no_fake_player_or_feed_link(self):
        html = render_page([], '')
        doc = Document(html)
        self.assertFalse(doc.tags('audio'))
        self.assertFalse(any(a.get('href') == 'feed.xml' for _, a in doc.elements))
        self.assertIn('First episode coming soon', html)

    def test_navigation_targets_exist_with_and_without_gallery(self):
        for gallery in ('', '<section id="our-story"></section>'):
            doc = Document(render_page([], gallery))
            ids = {a['id'] for _, a in doc.elements if 'id' in a}
            self.assertEqual(len(ids), len([a for _, a in doc.elements if 'id' in a]))
            for link in doc.tags('a'):
                if link.get('href', '').startswith('#'):
                    self.assertIn(link['href'][1:], ids)

    def test_episode_precedes_gallery_and_native_audio_is_labeled(self):
        html = render_page([sample()], '<section id="our-story">Gallery</section>')
        self.assertLess(html.index('id="2026-10-01-morning"'), html.index('<section id="our-story"'))
        audio, = Document(html).tags('audio')
        self.assertIn('controls', audio)
        self.assertNotIn('autoplay', audio)
        self.assertEqual(audio['preload'], 'none')
        self.assertIn('Synthetic renderer test', audio['aria-label'])
        self.assertEqual(audio['src'], 'episodes/2026-10-01-morning.mp3')

    def test_title_summary_and_source_cannot_inject_html(self):
        meta, audio, day = sample()
        meta.update(title='<img src=x onerror=alert(1)>', summary='<script>alert(1)</script>',
                    sources=['https://example.org/a?x=" onmouseover="alert(1)'])
        html = render_page([(meta, audio, day)], '')
        doc = Document(html)
        self.assertFalse(doc.tags('script'))
        self.assertEqual(len(doc.tags('img')), 1)
        self.assertFalse(any(k.startswith('on') for _, attrs in doc.elements for k in attrs))
        self.assertIn('&lt;script&gt;', html)
        source = [a for a in doc.tags('a') if a.get('target') == '_blank'][0]
        self.assertIn('noopener', source['rel'])
        self.assertIn('noreferrer', source['rel'])

    def test_all_fifty_supported_episodes_have_stable_links(self):
        from datetime import timedelta
        entries = []
        for n in range(50):
            meta, audio, day = sample()
            day += timedelta(days=n)
            meta.update(date=str(day), filename=f'{day}-morning.mp3')
            entries.append((meta, Path(meta['filename']), day))
        doc = Document(render_page(entries, ''))
        self.assertEqual(len(doc.tags('audio')), 50)
        self.assertEqual(len(doc.tags('article')), 50)
        self.assertEqual(len({a['id'] for a in doc.tags('article')}), 50)

    def test_real_build_copies_media_and_rss_sources_then_clears_stale_media(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            episodes = root / 'episodes'
            episodes.mkdir()
            meta, audio, day = sample()
            (episodes / audio.name).write_bytes(b'ID3' + bytes(4096))
            source = episodes / audio.with_suffix('.json').name
            source.write_text(json.dumps(meta))
            with patch.object(build_site, 'ROOT', root), patch.object(build_site, 'SITE', root / 'site'), patch.object(build_site, 'EPISODES', episodes):
                build_site.main()
                node = ET.parse(root / 'site/feed.xml').find('channel/item')
                self.assertIn(meta['sources'][0], node.findtext('description'))
                self.assertEqual(node.find('enclosure').attrib['length'], '4099')
                self.assertEqual((root / 'site/episodes' / audio.name).read_bytes(), (episodes / audio.name).read_bytes())
                self.assertTrue((root / 'site/assets/site.css').exists())
                source.unlink()
                build_site.main()
                self.assertFalse((root / 'site/feed.xml').exists())
                self.assertFalse((root / 'site/episodes').exists())

    def test_no_third_party_assets_or_executable_javascript(self):
        doc = Document(render_page([], ''))
        self.assertFalse(doc.tags('script'))
        self.assertFalse(any(a.get('src', '').startswith('http') for _, a in doc.elements))
        policy = next(a['content'] for a in doc.tags('meta') if a.get('http-equiv') == 'Content-Security-Policy')
        self.assertIn("default-src 'none'", policy)
        self.assertIn("media-src 'self'", policy)

    def test_keyboard_and_reduced_motion_support(self):
        html = render_page([], '')
        self.assertEqual(len(Document(html).tags('h1')), 1)
        self.assertIn('Skip to content', html)
        css = (build_site.ASSETS / 'site.css').read_text()
        self.assertIn('prefers-reduced-motion:reduce', css)
        self.assertIn(':focus-visible', css)

    def test_approved_gallery_bytes_and_no_exif(self):
        from zipfile import ZipFile
        from PIL import Image
        from io import BytesIO
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(build_site, 'SITE', Path(temp)):
                build_site.prepare_gallery()
            with ZipFile(build_site.ROOT / 'family-gallery.zip') as bundle:
                for number in range(1, 9):
                    name = f'photos/moment-{number:02d}.jpg'
                    original = ((build_site.ASSETS / "gallery-feature.jpg").read_bytes()
                                if number == 8 else bundle.read(name))
                    self.assertEqual(original, (Path(temp) / name).read_bytes())
                    with Image.open(BytesIO(original)) as image:
                        self.assertFalse(image.getexif())


if __name__ == '__main__':
    unittest.main()
