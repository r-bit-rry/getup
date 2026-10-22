# ADR-0006: Unknown never hides an event; only an explicit contradiction does

- **Status:** Accepted
- **Date:** 2026-10-18
- **Supersedes:** —
- **Superseded by:** —

## Context

Age restriction is absent from every structured source. In 44,770 characters of Leaan
standup copy there were zero references to audience age, and `18+` appeared in prose only
occasionally. Ticket availability is likewise only partially reported.

## Decision

A filter may remove an event only when a source explicitly states a value that excludes
it. Missing data never removes an event and is never rendered as a warning badge.
Absence of a chip is the "unknown" state.

Applied to age, availability, price and crowd alike.

One exception: a positive claim requires the fact. "Free only" asserts that an event is
free, so an unknown price does not pass it — the filter cannot claim what no source said.
That is still not hiding for missing data: the event is absent from that *claim*, not from
the unfiltered page, and ADR-0003/dedup and the drive cap keep treating it normally.

## Consequences

Filters are advisory rather than absolute: setting an age filter will not hide an event
whose age is unstated. This is intentional — a portal that silently drops events for missing
metadata fails its primary anti-goal (missing events).
