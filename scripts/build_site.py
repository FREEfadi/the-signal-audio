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
        field(node, "description", metadata["summary"])
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
# single, intentionally uploaded source; audio privacy gates stay unchanged.
PHOTO_DESCRIPTIONS = [
    "Together, dressed up for a special evening",
    "Watching an ocean sunset together",
    "Smiling together by the coast",
    "A sweet moment together outdoors",
    "A colorful tropical afternoon",
    "Together at an outdoor cafe",
    "A kiss beside a colorful love sculpture",
    "Sharing a smile on a night out",
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
        prominent = ' featured' if number == 1 else ''
        centered = ' centered' if number == 8 else ''
        cards.append(
            '<a class="memory' + prominent + centered + '" href="photos/' + filename
            + '" target="_blank" rel="noopener" aria-label="View photo '
            + str(number) + ' full size">'
            + '<img src="photos/' + filename + '" alt="'
            + escape(description) + '" loading="lazy" decoding="async">'
            + '</a>'
        )
    if not cards:
        return ""
    return (
        '<section class="gallery-section" aria-labelledby="gallery-title">'
        '<div class="gallery-overline">The moments behind the music</div>'
        '<h2 id="gallery-title">A little bit of us</h2>'
        '<p class="gallery-subtitle">A few favorite moments along the way.</p>'
        '<div class="gallery-grid">' + ''.join(cards) + '</div></section>'
    )


def index(items):
    cards = "".join(
        '<article class="episode"><span class="date">'
        + escape(meta["date"]) + " · " + escape(meta["edition"].title())
        + "</span><h2>" + escape(meta["title"])
        + "</h2><p>" + escape(meta["summary"])
        + '</p><audio controls preload="none" src="episodes/'
        + quote(audio.name) + '"></audio></article>'
        for meta, audio, _ in items[:8]
    )
    button = (
        '<a class="button" href="feed.xml">Open podcast RSS feed</a>'
        if items else '<span class="pending">Our first episode is coming soon.</span>'
    )
    gallery = photo_gallery()
    html = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Signal — Morning Audio Briefing</title>
<meta name="description" content="News, technology, and Fairfax County: a short public-news audio briefing.">
<style>
:root{color-scheme:dark}*{box-sizing:border-box}
body{margin:0;background:#102139;color:#e8f4fb;font:16px/1.6 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:800px;margin:auto;padding:50px 24px 75px}
.hero{display:flex;gap:28px;align-items:center;padding-bottom:44px;border-bottom:1px solid #365164}
.hero img{width:180px;height:180px;border-radius:20px;box-shadow:0 10px 35px #071625}
.kicker{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#9ed8ed;font-weight:700}
h1{font-size:clamp(40px,7vw,60px);letter-spacing:-.05em;line-height:1.07;margin:10px 0}
p{color:#c0d2df}.lead{font-size:19px}
.button{display:inline-block;background:#9ed8ed;color:#11263e;text-decoration:none;border-radius:9px;padding:12px 19px;font-weight:800}
.pending{border:1px solid #6d8c9d;border-radius:9px;padding:12px 19px;display:inline-block}
.episode{border-bottom:1px solid #355469;padding:24px 0}
.episode h2{margin:6px 0;font-size:22px}.date{color:#9ed8ed;font-size:13px}
.episode audio{width:100%}
.gallery-section{margin:42px 0 32px;padding:35px 0 37px;border-top:1px solid #355469;border-bottom:1px solid #355469}
.gallery-overline{font-size:12px;letter-spacing:.13em;text-transform:uppercase;color:#9ed8ed;font-weight:700}
.gallery-section h2{font-size:clamp(26px,5vw,36px);letter-spacing:-.025em;margin:5px 0 0}
.gallery-subtitle{margin:0 0 22px;font-size:15px}
.gallery-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:11px}
.memory{display:block;position:relative;overflow:hidden;aspect-ratio:1/1.1;border-radius:13px;background:#29435b;outline-offset:3px}
.memory img{display:block;width:100%;height:100%;object-fit:cover;object-position:center 30%;transition:transform .3s ease}
.memory:hover img{transform:scale(1.035)}
.memory.featured{grid-column:span 2;grid-row:span 2;aspect-ratio:auto}
.memory.featured img{object-position:center 25%}
.memory.centered{grid-column:1 / -1;max-width:260px;width:100%;justify-self:center}
.dedication{margin:45px 0 0;padding:25px 12px;border-top:1px solid #355469;text-align:center;color:#d4eaf5;font-size:15px;letter-spacing:.01em}
@media(max-width:580px){.gallery-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.memory{border-radius:11px}.memory.featured{grid-row:span 2}}
small{display:block;color:#9fb2c2;margin-top:46px}
@media(max-width:580px){.hero{display:block}.hero img{width:140px;height:140px}main{padding-top:30px}}
</style></head><body><main><header class="hero">
<img src="cover.jpg" width="180" height="180" alt="The Signal podcast artwork">
<div><div class="kicker">The Morning Signal · Audio Edition</div>
<h1>The Signal</h1><div class="lead">News. Tech. Fairfax County. Your day ahead, in audio.</div></div>
</header><p>Good stories, clear context, and the technology that matters. A short independent briefing focused on verified public news, local decisions, cybersecurity and gaming.</p>
""" + button + gallery + "<section>" + cards + """</section>
<p class="dedication">My first podcast webpage - made with love for Eliana 🤍</p>
</main></body></html>"""
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
