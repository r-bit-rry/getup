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
