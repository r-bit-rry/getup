# ADR-0003: Dedup: venue identity plus start time within ±30 minutes

- **Status:** Accepted
- **Date:** 2026-10-18
- **Supersedes:** —
- **Superseded by:** —

## Context

The same event arrives from ticketing platforms, aggregators, nightlife feeds and social
mirrors. The opposite error also exists: one title can play several cities on different
nights (30 of 53 distinct Leaan titles tour; MAD MOZART plays 7 cities). At a club, one
venue may post a single 22:00–04:00 night with three DJs, or split the day into a noon party
and an evening party.

## Decision

Merge two records when `venue_key` matches **and** start times are within ±30 minutes.
Never merge on overlapping time windows alone.

Ticketed events: the seller owns the record (ADR-0005). Free events merge on the rule above.

A noon party 12:00–20:00 and a night party 21:00–03:00 differ by nine hours at the start and
correctly stay separate. A club night and a DJ set inside it differ by an hour and correctly
stay separate.

## Consequences

Under-merging (a visible duplicate) is preferred to over-merging (a silently deleted
event). Genuine overlap at one venue will occasionally show two rows. Accepted.

## Known limitation

`חגית גינזבורג`, 2026-10-24 21:00 — Leaan sells it at `צוותא 2` for ₪89 and Biluim at
`צוותא תל אביב` for ₪119. The venue strings provision two different `venue_id`s
(`v_abbb77c465` and `v_f12491f371`), so the venue-key rule cannot see them as one event;
record ids are `v_abbb77c465|2026-10-24|21:00` and `v_f12491f371|2026-10-24|21:00`.
Both rows are left visible. Loosening the venue rule (fuzzy hall names) would merge the
many genuinely different halls that share a building, so under-merging stands.
