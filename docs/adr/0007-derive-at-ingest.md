# ADR-0007: Derived signals are computed at ingest and cached in the JSON

- **Status:** Accepted
- **Date:** 2026-10-18
- **Supersedes:** —
- **Superseded by:** —

## Context

Several requested signals (daypart, expensive, free-until, commitment, format, notable)
are not fields in any source. They are derivable, but deriving them in the browser on every
load costs CPU, makes output non-reproducible, and scatters the rules across the client.

## Decision

The agent computes them once at ingest and writes them into the event record. The browser
reads them. Classification is LLM-backed for `format` / `scene` / `crowd` against the closed
vocabulary in the design doc, and rule-based for the numeric signals.

## Consequences

A rule change requires a re-run over retained data. Because the archive keeps full
records, backfills are possible. The browser cannot re-derive, so a stale field stays stale
until the next scan.

**Amendment 2026-10-22 — `commitment`:** dropped the "ticketed and >48 h away" clause. In a
7-day view every ticketed event is more than 48 hours away, so the clause fired on almost
every row and the signal stopped distinguishing anything. `plan_ahead` now means festival/rave
format, drive ≥ 60 min, or a fixed-seat venue (theatre, orchestra). Fixture records were
recomputed; the decision and the rest of the ingest rule are unchanged.
