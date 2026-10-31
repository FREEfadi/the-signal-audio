# Approved public podcast episodes only

This folder is public. NEVER upload private newsletter emails, calendars, family information, work-confidential FCPS details, Gemini API keys, or private testing artifacts.

When a real public-news episode is ready, manually verify its entire MP3 and metadata and commit matching:
- `YYYY-MM-DD-morning.mp3` (or `midday`)
- `YYYY-MM-DD-morning.json`

JSON fields: `date`, `edition`, `title`, `summary`, `filename`, `sources` (real public HTTPS news sources), `public_only: true`, `privacy_reviewed: true`.

The build deliberately refuses unreviewed metadata and broken or missing MP3 audio. Metadata keyword screening is not a substitute for listening to the complete recording and checking it for privacy issues.

No real public-news episode has been published yet.
