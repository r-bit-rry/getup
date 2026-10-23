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
PYTHONPATH=. python3 -m tools.getup labels --labels replies.jsonl   # apply label replies, one JSON per line
```

## Intake: issues become drafts

Three forms in `.github/ISSUE_TEMPLATE/` are open to anyone: `event.yml` (an
event nobody listed), `source.yml` (a source worth adding) and `prefs.yml` (a
never/always rule). Ingestion is not: only an issue whose `author_association` is
`OWNER` or `MEMBER` is processed. A stranger's issue is never processed and never
answered.

The poll reads open issues labelled `intake`, never the ones already labelled
`processed`. An event issue becomes one canonical draft in `data/human.json`; a
prefs issue writes its rule to `prefs.json`. A `source.yml` issue stores nothing:
it only gets a receipt comment with the source request, so those leads live in the
issue thread, not in the site's data. On every poll it also asks the API about the
issue numbers already named by `data/human.json` and by the prefs rules, and
removes the draft or rule of any issue now closed. The receipt comment quotes the
record; the labels are the only state.

One-time label bootstrap — the poll verifies these and refuses to run without
them, because a form silently drops a label the repo does not have:

```sh
gh label create intake
gh label create processed
gh label create needs-info
gh label create "intake:prefs"
```

Daily, one command. The poll needs the repo and a token (`gh auth token`
prints one):

```sh
export GETUP_REPO=owner/name
export GETUP_GITHUB_TOKEN=...
scripts/daily.sh --dry-run   # four steps, prints what it would stage
scripts/daily.sh             # intake → build → coverage → archive → commit → push
```

The poll only edits the working tree: the page changes when its output is
committed and pushed, which is what the script does. `intake` runs before
`build`, so a new event appears on the same day. Scheduling it on the phone,
and what a failure looks like, is in `docs/operations.md`.

To correct a processed issue, remove its `processed` label and edit the body; the
next poll replaces that issue's draft, or its prefs rule, and the build puts the
human row above the scanned one. A start-time correction beyond ±30 minutes is a
second row, not a replacement: dedup only merges two starts within that window
(ADR-0003), so close the old issue or edit its time as well.

Two ways to retract: close the issue — the next poll asks about that issue number
and deletes its draft from `data/human.json` and any prefs rule it wrote — or
delete the issue's key from `data/human.json` (or its rule from `prefs.json`) by
hand and commit.

## prefs.json

The browser applies these rules on reload; the pipeline never evaluates one. Each
entry is one rule, and a rule with both fields is an AND:

```json
{"never": [{"venue_id": "v_zionist_america_tlv"}], "always": [{"artist": "The Cure"}]}
```

| Field | Meaning |
|---|---|
| `venue_id` | a venue id from `venue/venues.json`, as written to the site |
| `artist` | an event title, exact after normalization (no fuzzy match) |

At least one field per rule is required. `never` hides the matching events;
`always` marks matching events notable. `never` is applied first, so an event
that matches both is hidden: `always` does not override `never`. The file is read
by `src/prefs.js` in the browser on reload — no rescan, no rebuild.

A rule is global: it applies in every reader's browser, not just the issue
author's. A `prefs.yml` issue writes its rule to this file, keyed by the issue
number, and confirms it in the issue; re-polling a corrected issue replaces that
rule instead of appending a second one. A venue rule may only name a venue
already in `venue/venues.json`; an unknown venue is not guessed and not
provisioned: the issue is answered with `needs-info` instead.

Exit codes: `0` ok · `1` bad arguments · `2` a source failed/partial or a bad
`--sources`/`--today` · `3` coverage missed a major venue · `4` tz data missing
· `5` GitHub API or token failure, a corrupt `prefs.json`/`venues.json`/
`human.json`, or one of them unwritable (intake).

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
