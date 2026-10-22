# ADR-0012: Notability from touring × venue tier × price; weekly coverage alarm

- **Status:** Accepted
- **Date:** 2026-10-18
- **Supersedes:** —
- **Superseded by:** —

## Context

The second anti-goal is missing high-profile events. Leaan exposes no popularity signal:
`promoted`, `last_hour_views`, `special_event` and `subscription` were false or zero across
all sampled events. What does exist: 30 of 53 distinct titles play ≥2 cities, venues differ
enormously in tier, and price is distributed (median ₪129, p90 ₪199, max ₪250).

## Decision

`notable = ticketing source AND (touring ≥2 cities OR venue.tier == major OR price ≥ ₪200)`.

`tools/coverage.py` reports, for every `tier = major` venue, whether any event referenced it
in the last 14 days, and writes misses into `data/index.json`. The portal shows them as one
quiet footer line — never a filter, never an interruption.

## Consequences

Notability is a proxy and will over-rate tribute shows and under-rate a small room with a
significant artist. The coverage alarm thresholds (14 days, tier assignment) need calibration
against real weeks before they can be trusted, and a noisy alarm is worse than none.

## Amendment — 2026-10-22, measured notability rate on the 2026-10-21 capture

On the 2026-10-21 capture, **50 of the 84 served records were `notable` (60%)**; **45 of those
50 came from the touring clause alone**, because 22 distinct titles produced those 50 rows.

The flag is not rendered in the UI and is used only to break same-day ordering ties, so a 60%
rate is not a user-visible defect. It is still too loose to be a signal: a title touring two
cities marks every one of its rows notable, every night.

Two candidate fixes, in order of preference:

1. Raise the touring threshold (three or more cities) so a two-city tour stops qualifying.
2. Mark a title notable only at its first upcoming showing, so one tour contributes one row.

Neither is applied here — this amendment records the measurement for the decision, not a change
to the rule.
