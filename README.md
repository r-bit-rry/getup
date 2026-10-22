# GetUp

A Hebrew, RTL live-events portal for Israel. List-first: a dense table and a
sticky map on desktop, one card per event on mobile.

Static site, no build step, no runtime dependencies. A separate agent scans the
sources and commits JSON; the site renders it.

```
index.html  styles.css  app.js     the site
src/                               pure modules (format, data, filters, chips, render, prefs, distance, map)
data/YYYY-MM-DD.json               one file per date, 30-day horizon
data/index.json                    manifest: dates, counts, source status, coverage
venue/venues.json                  venue registry — identity, city, point, parking, access
prefs.json                         never / always rules, applied in the browser
tools/getup/                       the ingestion pipeline (Python 3.14, stdlib only)
docs/                              spec, ADRs, plans, research captures
assets/                            vendored Rubik, Secular One, MapLibre 6
```

## Run the site

```sh
python3 -m http.server 8080
# http://localhost:8080
```

Everything is public by design (ADR-0008) — the site and the data are served
from a public GitHub repository.

## Run the pipeline

Python 3.14, standard library only. No install.

```sh
PYTHONPATH=. python3 -m tools.getup build            # scan → normalize → dedup → derive → write
PYTHONPATH=. python3 -m tools.getup build --from-dir docs/research/2026-10-21   # offline, from a capture
PYTHONPATH=. python3 -m tools.getup coverage         # 14-day alarm per major venue
PYTHONPATH=. python3 -m tools.getup archive          # roll days older than 90 into archive/
PYTHONPATH=. python3 -m tools.getup pending          # titles awaiting classification
PYTHONPATH=. python3 -m tools.getup labels           # apply the label cache
```

Exit codes: `0` ok · `1` bad arguments · `2` a source failed/partial or a bad
`--sources`/`--today` · `3` coverage missed a major venue · `4` tz data missing
· `5` GitHub API or token failure (intake).

A source that yields nothing does **not** empty the portal: the write and the
future-day prune are gated on tallied survivors, not on transport status.

Live source tests are gated: `GETUP_LIVE=1 python3 -m unittest discover -s tests_py`.

## Tests

```sh
node --test                                  # client, no dependencies
python3 -m unittest discover -s tests_py     # pipeline
```

## Decisions

`docs/superpowers/specs/2026-10-18-getup-design.md` is the design;
`docs/adr/` holds the twelve decisions it rests on. Two carry dated
amendments recorded against real measurements: ADR-0007 (`plan_ahead`) and
ADR-0012 (`notable`).

## Known limits

- Venue coordinates for most venues are **city centroids**, flagged on the
  record as `drive_approx` and rendered `~`. The map is honest about names,
  not precise about addresses.
- Some events have no place in their source; they publish with `city: null`
  and no drive time rather than a guessed one.
- One duplicate survives dedup because two sources give the same act different
  venue ids (recorded in ADR-0003).
- The catalogue is as thin as its sources: three adapters today.
