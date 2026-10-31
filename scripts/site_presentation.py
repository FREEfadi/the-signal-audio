"""Presentation only; approval, media copying, and RSS remain in build_site."""
from html import escape
from pathlib import Path
from string import Template
from urllib.parse import quote, urlsplit

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def episode_card(item, featured=False):
    meta, audio, day = item
    identity = f"{meta['date']}-{meta['edition']}"
    label = "Latest episode" if featured else meta["edition"].title() + " edition"
    links = []
    for number, url in enumerate(meta.get("sources", []), 1):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname:
            continue
        links.append(
            '<li><a href="' + escape(url, quote=True)
            + '" target="_blank" rel="noopener noreferrer">'
            + escape(parsed.hostname.removeprefix("www."))
            + '<span aria-hidden="true"> ↗</span><span class="sr-only">, source '
            + str(number) + ', opens in a new tab</span></a></li>'
        )
    sources = ('<details class="sources"><summary>Reporting &amp; sources <span aria-hidden="true">+</span></summary>'
               '<ol>' + ''.join(links) + '</ol></details>') if links else ''
    return (
        '<article class="episode' + (' episode-featured' if featured else '')
        + '" id="' + identity + '" aria-labelledby="title-' + identity + '">'
        + '<div class="episode-meta"><span>' + escape(label) + '</span>'
        + '<time datetime="' + escape(meta['date']) + '">' + day.strftime('%B %d, %Y') + '</time></div>'
        + '<h3 id="title-' + identity + '">' + escape(meta['title']) + '</h3>'
        + '<p>' + escape(meta['summary']) + '</p>'
        + '<audio controls preload="none" aria-label="Play ' + escape(meta['title'], quote=True)
        + '" src="episodes/' + quote(audio.name) + '">'
        + 'Your browser does not support audio. <a href="episodes/' + quote(audio.name)
        + '">Download this episode</a>.</audio>'
        + '<a class="download" href="episodes/' + quote(audio.name) + '" download>Download MP3 <span aria-hidden="true">↓</span></a>'
        + sources + '</article>'
    )


def render_page(items, gallery):
    if items:
        episodes = ''.join(episode_card(item, index == 0) for index, item in enumerate(items[:8]))
        if len(items) > 8:
            episodes += '<details class="archive"><summary>Earlier episodes</summary>' + ''.join(episode_card(item) for item in items[8:]) + '</details>'
        status = 'The latest briefing is ready'
        primary = '<a class="button button-light" href="#listen">Listen to the latest <span aria-hidden="true">↗</span></a>'
        follow = '<a class="text-link" href="feed.xml">Podcast RSS <span aria-hidden="true">↗</span></a>'
        feed_link = '<link rel="alternate" type="application/rss+xml" title="The Signal" href="feed.xml">'
        listening_note = '<p class="section-note">Listen here or open the <a href="feed.xml">RSS feed</a> in a podcast app that supports subscription by URL.</p>'
    else:
        status = 'First episode coming soon'
        primary = '<a class="button button-light" href="#about">Meet The Signal <span aria-hidden="true">↗</span></a>'
        follow = '<a class="text-link" href="#our-story">A little bit of us <span aria-hidden="true">↓</span></a>' if gallery else ''
        feed_link = ''
        listening_note = '<p class="section-note">A short pause before we press play.</p>'
        episodes = '''<div class="coming-soon">
          <div class="record-symbol" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div>
          <div><p class="eyebrow">In the making</p><h3>Good mornings start here.</h3>
          <p>Our first public episode is on its way. When it arrives, you’ll find the audio and the stories behind it right here.</p></div>
          <span class="status-label"><span aria-hidden="true"></span>Coming soon</span>
        </div>'''
    template = Template((ASSETS / 'page.html').read_text(encoding='utf-8'))
    return template.substitute(
        feed_link=feed_link, status=status, primary=primary, follow=follow,
        episodes=episodes, listening_note=listening_note, gallery=gallery,
        gallery_nav='<a href="#our-story">Our story</a>' if gallery else '',
    )
