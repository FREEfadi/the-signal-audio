import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET
from scripts import build_site


class SiteTests(unittest.TestCase):
    def test_no_episode_publishes_no_feed(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(build_site, "SITE", Path(d)/"site"), patch.object(build_site, "EPISODES", Path(d)/"episodes"):
                (Path(d)/"episodes").mkdir()
                build_site.main()
                self.assertTrue((Path(d)/"site"/"index.html").exists())
                self.assertFalse((Path(d)/"site"/"feed.xml").exists())
                image = (Path(d)/"site"/"cover.jpg").read_bytes()
                self.assertTrue(image.startswith(b"\xff\xd8\xff"))
                from PIL import Image
                with Image.open(Path(d)/"site"/"cover.jpg") as art:
                    self.assertEqual(art.size, (1600, 1600))

    def test_approval_gate(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            (folder/"2026-10-31-morning.json").write_text('{"public_only":false}')
            with patch.object(build_site, "EPISODES", folder):
                with self.assertRaises(ValueError):
                    build_site.approved_episodes()

    def test_feed_format(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(build_site, "SITE", Path(d)):
                sample = {"date":"2026-10-31", "edition":"morning", "title":"The Signal morning news", "summary":"A sample public news episode."}
                audio = Path(d)/"2026-10-31-morning.mp3"
                audio.write_bytes(b"ID3" + bytes(2048))
                build_site.feed([(sample, audio, build_site.datetime(2026,10,31).date())])
                item = ET.parse(Path(d)/"feed.xml").getroot().find("channel/item")
                self.assertEqual(item.find("enclosure").get("length"), str(audio.stat().st_size))
                self.assertTrue(item.find("pubDate").text.endswith("-0400"))
                block = ET.parse(Path(d)/"feed.xml").getroot().find("channel/{http://www.itunes.com/dtds/podcast-1.0.dtd}block")
                self.assertEqual(block.text,"Yes")


if __name__ == "__main__":
    unittest.main()
