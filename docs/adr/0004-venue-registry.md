# ADR-0004: venues.json keyed on a geocoded point is the only place identity

- **Status:** Accepted
- **Date:** 2026-10-18
- **Supersedes:** —
- **Superseded by:** —

## Context

Venue strings cannot be compared. In a 195-event sample, `היכל התרבות` appears in 16
different cities, `בית יד לבנים` in two, `סינמטק` in two. The same city also arrives spelled
two ways (`פתח תקווה` / `פתח תקוה`, `מעלות תרשיחא` / `מעלו תרשיחא`, `תל אביב` /
`תל אביב-יפו`).

## Decision

One registry, `venue/venues.json`, holds id, canonical name, aliases, city, lat/lon,
tier (major|mid|room), parking, accessibility, transport and social links. Events reference
`venue_id` and never carry an authoritative venue string.

Geocoding happens once per venue using the `"venue, city"` query form and is cached forever.
Alias resolution and city spelling collapse happen at ingest, once, at the venue.

## Consequences

The registry acquires a maintenance cost: new venues need an entry before their events
render well. The agent may create provisional entries, but a venue with no geocode must be
flagged rather than silently rendered without a map pin.
