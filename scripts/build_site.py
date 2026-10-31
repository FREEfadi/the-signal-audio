#!/usr/bin/env python3
"""Build public-news-only podcast website, original cover, and RSS feed.

No email, calendars, API keys, or private audio files are read. The RSS feed
doesn't exist until a genuinely reviewed public-news MP3 is supplied.
"""
import json
import math
import re
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, time, timezone
from email.utils import format_datetime
from html import escape
from pathlib import Path
from zipfile import ZipFile
from urllib.parse import quote
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

try:
    from .site_presentation import ASSETS, render_page
except ImportError:
    from site_presentation import ASSETS, render_page

BASE = "https://freefadi.github.io/the-signal-audio"
ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
EPISODES = ROOT / "episodes"
ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM = "http://www.w3.org/2005/Atom"
ET.register_namespace("itunes", ITUNES)
ET.register_namespace("atom", ATOM)
REJECT = [
    r"\b(?:sayuri|cookie|eliana|thoreau|fadirabadi|falrabadi)\b",
    r"\b(?:my|our)\s+(?:family|wife|daughter|son|calendar|appointment)\b",
    r"\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b",
]


def cover_image(target):
    """Generate original 1600x1600 podcast artwork without third-party assets."""
    side = 1600
    picture = Image.new("RGB", (side, side), (18, 37, 62))
    painter = ImageDraw.Draw(picture)
    for y in range(side):
        fraction = y / side
        painter.line((0, y, side, y), fill=(
            round(16 + 5 * fraction),
            round(33 + 12 * fraction),
            round(56 + 22 * fraction)
        ))
    for radius in (570, 485, 400):
        painter.ellipse(
            (800-radius, 720-radius, 800+radius, 720+radius),
            outline=(38, 101, 130), width=5
        )
    for n in range(27):
        x = 350 + 34 * n
        amp = 76 + int(230 * abs(math.sin(n * .71)) * abs(math.cos(n * .31)))
        painter.rounded_rectangle(
            (x, 730-amp, x+17, 730+amp), radius=8, fill=(137, 217, 239)
        )
    bold_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]
    normal_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    def font(paths, size):
        for path in paths:
            if Path(path).exists():
                return ImageFont.truetype(path, size)
        return ImageFont.load_default()
    painter.text(
        (800, 1200), "THE SIGNAL", anchor="mm",
        fill=(239, 248, 253), font=font(bold_candidates, 160)
    )
    painter.text(
        (800, 1350), "NEWS  /  TECH  /  LOCAL", anchor="mm",
        fill=(137, 217, 239), font=font(normal_candidates, 45)
    )
    picture.save(target, "JPEG", quality=90, optimize=True)


def approved_episodes():
    items = []
    EPISODES.mkdir(exist_ok=True)
    for itemfile in sorted(EPISODES.glob("*.json")):
        metadata = json.loads(itemfile.read_text(encoding="utf-8"))
        if metadata.get("public_only") is not True or metadata.get("privacy_reviewed") is not True:
            raise ValueError(f"Not explicitly approved for publication: {itemfile.name}")
        edition = metadata.get("edition")
        if edition not in ("morning", "midday"):
            raise ValueError(f"Unexpected edition: {itemfile.name}")
        date_str = metadata.get("date")
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid date: {itemfile.name}") from exc
        title = metadata.get("title", "")
        summary = metadata.get("summary", "")
        filename = f"{date_str}-{edition}.mp3"
        if metadata.get("filename") != filename or itemfile.stem != f"{date_str}-{edition}":
            raise ValueError(f"Unsafe or mismatched filename: {itemfile.name}")
        if not isinstance(title, str) or not 10 <= len(title) <= 140:
            raise ValueError(f"Invalid title: {itemfile.name}")
        if not isinstance(summary, str) or not 15 <= len(summary) <= 550:
            raise ValueError(f"Invalid summary: {itemfile.name}")
        if any(
            re.search(pattern, text, re.IGNORECASE)
            for pattern in REJECT for text in (title, summary)
        ):
            raise ValueError(f"Possible personal details in public metadata: {itemfile.name}")
        sources = metadata.get("sources")
        if not isinstance(sources, list) or not sources or any(
            not isinstance(url, str) or not url.startswith("https://")
            for url in sources
        ):
            raise ValueError(f"Public sources required: {itemfile.name}")
        audio = EPISODES / filename
        if not audio.is_file() or not 1500 <= audio.stat().st_size <= 100_000_000:
            raise ValueError(f"Missing or invalid MP3: {filename}")
        with audio.open("rb") as stream:
            prefix = stream.read(3)
            if prefix != b"ID3":
                stream.seek(0)
                start = stream.read(2)
                if len(start) < 2 or start[0] != 0xFF or (start[1] & 0xE0) != 0xE0:
                    raise ValueError(f"Not an MP3 file: {filename}")
        items.append((metadata, audio, date))
    if len(items) > 50:
        raise ValueError("50-episode cap exceeded; archive older episodes first.")
    return sorted(items, key=lambda item: (item[2], item[0]["edition"]), reverse=True)


def feed(items):
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    def field(parent, key, value):
        ET.SubElement(parent, key).text = value
    field(channel, "title", "The Signal")
    field(channel, "link", BASE + "/")
    field(channel, "description",
          "Public news, Fairfax County, AI, technology, cybersecurity, and gaming in a concise audio briefing.")
    field(channel, "language", "en-us")
    field(channel, "lastBuildDate", format_datetime(datetime.now(timezone.utc)))
    field(channel, f"{{{ITUNES}}}author", "The Signal")
    field(channel, f"{{{ITUNES}}}explicit", "false")
    field(channel, f"{{{ITUNES}}}summary",
          "Independent public-news audio, with no private calendars or confidential work records.")
    field(channel, f"{{{ITUNES}}}type", "episodic")
    field(channel, f"{{{ITUNES}}}block", "Yes")
    ET.SubElement(channel, f"{{{ITUNES}}}category", {"text": "News"})
    ET.SubElement(channel, f"{{{ITUNES}}}image", {"href": BASE + "/cover.jpg"})
    ET.SubElement(channel, f"{{{ATOM}}}link", {
        "rel": "self", "href": BASE + "/feed.xml", "type": "application/rss+xml"
    })
    for metadata, audio, date in items:
        node = ET.SubElement(channel, "item")
        field(node, "title", metadata["title"])
        # Provide transparent source references in podcast show notes.
        # The RSS renderer XML-escapes content automatically.
        show_notes = metadata["summary"] + "\n\nSources:\n" + "\n".join(metadata.get("sources", []))
        field(node, "description", show_notes)
        field(node, f"{{{ITUNES}}}explicit", "false")
        field(node, "guid", f'the-signal-{metadata["date"]}-{metadata["edition"]}')
        local_hour = 7 if metadata["edition"] == "morning" else 12
        published = datetime.combine(date, time(local_hour), ZoneInfo("America/New_York"))
        field(node, "pubDate", format_datetime(published))
        ET.SubElement(node, "enclosure", {
            "url": BASE + "/episodes/" + quote(audio.name),
            "length": str(audio.stat().st_size),
            "type": "audio/mpeg"
        })
    ET.ElementTree(rss).write(SITE / "feed.xml", encoding="utf-8", xml_declaration=True)


# Optional, public family gallery. Owner-provided family-gallery.zip is the
# intentionally uploaded source. The owner-approved eighth-photo replacement
# is assets/gallery-feature.jpg; audio privacy gates stay unchanged.
PHOTO_DESCRIPTIONS = [
    "Together, dressed up for a special evening",
    "Watching an ocean sunset together",
    "Smiling together by the coast",
    "A sweet moment together outdoors",
    "A colorful tropical afternoon",
    "Together at an outdoor cafe",
    "A kiss beside a colorful love sculpture",
    "Together, dressed up and sharing a happy moment",
]


def prepare_gallery():
    """Read a voluntarily uploaded family-gallery.zip and publish the eight approved JPGs.

    The zip stays public in GitHub. Never read arbitrary names or filesystem paths
    from it; filenames are fixed, and all source photos were stripped of EXIF.
    """
    archive = ROOT / "family-gallery.zip"
    destination = SITE / "photos"
    if destination.exists():
        shutil.rmtree(destination)
    if not archive.is_file():
        # No photos yet; leave site functional without broken images.
        print("Family gallery archive not uploaded yet; skipping gallery.")
        return
    with ZipFile(archive, "r") as bundle:
        expected = [f"photos/moment-{i:02d}.jpg" for i in range(1, 9)]
        names = {info.filename: info for info in bundle.infolist()}
        missing = [name for name in expected if name not in names]
        if missing:
            raise ValueError("Gallery archive is incomplete: " + ", ".join(missing))
        destination.mkdir(parents=True)
        for name in expected:
            info = names[name]
            if info.file_size > 2_000_000:
                raise ValueError("Gallery image exceeds 2 MB: " + name)
            photo = bundle.read(info)
            if len(photo) != info.file_size or not photo.startswith(b"\xff\xd8\xff"):
                raise ValueError("Invalid JPEG inside gallery archive: " + name)
            if name == "photos/moment-08.jpg":
                photo = (ASSETS / "gallery-feature.jpg").read_bytes()
                if len(photo) > 2_000_000 or not photo.startswith(b"\xff\xd8\xff"):
                    raise ValueError("Invalid approved gallery replacement.")
            (destination / Path(name).name).write_bytes(photo)
    print("Published eight approved gallery photographs.")


def photo_gallery():
    """Show all available photos, without broken links before upload."""
    source = SITE / "photos"
    cards = []
    for number, description in enumerate(PHOTO_DESCRIPTIONS, 1):
        filename = f"moment-{number:02d}.jpg"
        if not (source / filename).is_file():
            continue
        with Image.open(source / filename) as photo:
            width, height = photo.size
        prominent = ' featured' if number == 1 else ''
        centered = ' centered' if number == 8 else ''
        cards.append(
            '<a class="memory' + prominent + centered + '" href="photos/' + filename
            + '" target="_blank" rel="noopener" aria-label="View photo '
            + str(number) + ' full size">'
            + '<img src="photos/' + filename + '" alt="'
            + escape(description) + '" width="' + str(width) + '" height="' + str(height)
            + '" loading="lazy" decoding="async">'
            + '</a>'
        )
    if not cards:
        return ""
    return (
        '<section class="gallery-section wrap" id="our-story" aria-labelledby="gallery-title">'
        '<div class="gallery-heading"><div><p class="eyebrow">The people behind The Signal</p>'
        '<h2 id="gallery-title">A little bit of us</h2>'
        '</div><p>Big adventures. Little moments. A few favorites from our life together.</p></div>'
        '<div class="gallery-grid">' + ''.join(cards) + '</div><p class="gallery-caption">The best part of the story is sharing it.</p></section>'
    )


def index(items):
    """Render the editorial website without changing publication or RSS rules."""
    target = SITE / "assets"
    target.mkdir(exist_ok=True)
    shutil.copy2(ASSETS / "site.css", target / "site.css")
    html = render_page(items, photo_gallery())
    (SITE / "index.html").write_text(html, encoding="utf-8")


def main():
    SITE.mkdir(exist_ok=True)
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    cover_image(SITE / "cover.jpg")
    items = approved_episodes()
    target = SITE / "episodes"
    if target.exists():
        shutil.rmtree(target)
    if items:
        target.mkdir()
        for metadata, audio, day in items:
            shutil.copy2(audio, target / audio.name)
        feed(items)
    else:
        (SITE / "feed.xml").unlink(missing_ok=True)
    prepare_gallery()
    index(items)
    print(f'Site generated: {len(items)} approved episodes; feed exists: {(SITE / "feed.xml").exists()}')


if __name__ == "__main__":
    main()
