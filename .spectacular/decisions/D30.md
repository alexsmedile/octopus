# D30 — Datetime precision differs by file type

- Session frontmatter: `YYYY-MM-DDTHH:MM:SS` (with seconds, ISO 8601 datetime).
- Memory entries: `YYYY-MM-DD HH:MM` (minute precision, no seconds).
- Memory entries are journal-style — minute precision is sufficient and reads cleaner.
