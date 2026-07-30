# BooleanRazor report

`data/project.json` is the only hand-edited report content. The HTML site and
the four concise Markdown indexes are generated and must not be edited by
hand.

```bash
make report
make report-check
.venv/bin/python -m http.server 8765 --directory reports/site
```

The report is offline-first: it uses no CDN, tracker, external font, runtime
fetch, public benchmark mount, or sealed evidence. Its landing page cites the
reviewed report/autoresearch examples with explicit adaptation-only notes;
those links are references, not loaded assets or copied implementation.
