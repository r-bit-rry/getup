# ADR-0011: Design system: Rubik + Secular One, orange/blue, dense rows

- **Status:** Accepted
- **Date:** 2026-10-18
- **Supersedes:** —
- **Superseded by:** —

## Context

The portal is scanned daily at a glance, primarily on a phone, sometimes at 23:00. It
must read as nightlife without becoming a poster. The reference systems (Sentry for density
and Rubik, Airtable for structured-data chips) supplied vocabulary, not colours.

## Decision

Rubik variable (Hebrew + Latin, tabular numerals) for everything; Secular One for the
wordmark only. `#EA580C` for events, `#2563EB` for map/cool, `#FFF7ED` day base, `#0B1120`
night base. 40 px rows, 13 px body, 11 px chips, 8 px spacing base.

Two chip axes, two colours: scene blue, crowd orange. Chips carry icon **and** Hebrew label.
Hierarchy is weight + size + colour, never uppercase.

## Consequences

A single family limits display expressiveness. Dark text on orange is required for
contrast; white-on-orange fails at small sizes.
