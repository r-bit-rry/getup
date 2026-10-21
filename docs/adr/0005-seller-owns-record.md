# ADR-0005: Ticket seller owns ticketed records; aggregators become enrichment

- **Status:** Accepted
- **Date:** 2026-10-18
- **Supersedes:** —
- **Superseded by:** —

## Context

For a ticketed show, several sources carry the same event. The seller has the authoritative
time, price and availability. The aggregator frequently carries better prose: parking,
accessibility, doors-open times, audience hints. Discarding the aggregator loses real
information; keeping it as a second row creates duplicates.

## Decision

The ticket seller is the canonical record for a ticketed event. An aggregator's copy is
attached to it as `enrichment[]` — its notes, description and links — and never appears as
its own row.

If no seller record exists yet, the aggregator record stands with
`source.class = "aggregator"` and is replaced when that seller is scanned.

## Consequences

Enrichment is additive and may contradict the seller. The seller's value wins on time,
price and availability; enrichment only contributes notes and links.
