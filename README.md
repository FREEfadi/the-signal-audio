# The Signal — Public Audio Site

**Public media only.** This repository is intended for The Signal podcast website, original show artwork, and later a public-news-only RSS feed.

- Website: https://freefadi.github.io/the-signal-audio/
- Podcast RSS (after first approved real episode): https://freefadi.github.io/the-signal-audio/feed.xml
- Private source and Gemini API secret: stored separately in `FREEfadi/the-signal-podcast`, never copied here.

## Deployment
GitHub Actions automatically builds the original 1600×1600 cover and publishes the site using GitHub Pages. The site explicitly shows **Coming soon** until a real, approved public-news recording has been published. No fabricated episodes or personal audio.

## Safety
Never commit private emails, personal calendars, family information, student/staff data, work-confidential information, API keys, or unreviewed recordings. `privacy_reviewed` and keyword checks are not proof that a transcript is safe to publish. A human must check audio before publication.

When public audio is ready, put matching `YYYY-MM-DD-morning.mp3` and `YYYY-MM-DD-morning.json` (or `midday`) files under `episodes/`. Include date, title, edition, filename, summary, sources, public_only and privacy_reviewed. Build failures stop publication.

Use Settings → Pages → Source → **GitHub Actions**. No billing or external hosting required.

## Family photo gallery (one-file upload)
The website shows a responsive gallery of eight photos plus the dedication:
> My first podcast webpage - made with love for Eliana

Upload **one binary file**, `family-gallery.zip`, to the top level of this public repository, using the GitHub website at https://github.com/FREEfadi/the-signal-audio/upload/main. The website workflow automatically extracts the eight pre-optimized images into the published website. The photo gallery stays hidden until the archive is present, but the dedication is already live.

The photo package was prepared from the eight images explicitly provided by the site owner. The site checks for precisely `photos/moment-01.jpg` through `photos/moment-08.jpg` inside the ZIP. All original EXIF/GPS metadata has been removed from the optimized web copies.

**Important:** The photos and ZIP become publicly accessible and downloadable after upload. Do not upload originals containing sensitive metadata or photos not intended for public view.
