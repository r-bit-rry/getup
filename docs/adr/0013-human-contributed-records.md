# ADR-0013: Human contributions are drafts in `data/human.json`, placed every build

- **Status:** Accepted
- **Date:** 2026-10-23
- **Supersedes:** —
- **Superseded by:** —

## Context

Issues are the only way a human adds or corrects an event (§7.9). The obvious place to
write the result is the day file — but a day file is a pure function of the scan, and the
next build overwrites it. A human row written there would survive one night at most. The
record also needs a venue, city, coordinates and drive time, none of which the form asks
for and all of which the registry already owns.

## Decision

Store each ingested event issue as a **draft** in `data/human.json`, keyed by issue
number, with `source.class = "human"`. On every build `build.place` resolves it through
the venue registry exactly like a scanned draft — venue identity, `city`, `lat`, `lon`,
`drive_min`, `coords_source` — and `dedup.RANK` puts `human` above `ticketing`, so at the
same venue within ±30 minutes the human record is the row and the machine copy becomes
`enrichment`.

Retraction is the issue's state: the poll asks about each issue number already named in
the store and deletes the draft when that issue is closed. Ingestion is guarded on
`author_association` in {OWNER, MEMBER} (ADR-0008).

## Consequences

A correction survives every future scan, and a venue provisioned after ingestion gains
its coordinates on the next build with no re-issue. `data/human.json` is committed data,
not a day file — it does not match the day-file pattern and nothing enumerates `data/` to
find it. Closing an issue is the delete; there is no other undo. A human draft with a
venue the registry cannot place still publishes with null minutes and is counted in
`unpinned`, so the guarantee is authority, not completeness. Retraction needs the API to
answer: offline, the poll fails closed and the draft stays one more night.
