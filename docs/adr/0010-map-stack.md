# ADR-0010: MapLibre GL 6 with OpenFreeMap tiles; OSM's own tiles rejected

- **Status:** Accepted
- **Date:** 2026-10-18
- **Supersedes:** —
- **Superseded by:** —
- **Confirmed:** 2026-10-23 — MapLibre 6 + OpenFreeMap rendering in the deployed page, Hebrew labels correct RTL.

## Context

Verified 2026-10-18: OpenFreeMap's public instance is free with no key and no request
limit. Its tiles carry `name:he` — a Netanya z13 tile contained 163 Hebrew strings. MapLibre
6 does its own bidi reordering, so Hebrew renders correctly without the deprecated
`setRTLTextPlugin`. `tile.openstreetmap.org` is donation-funded, has no SLA, forbids bulk and
offline use, and blocks applications that grow.

## Decision

MapLibre GL JS 6.x + OpenFreeMap (positron-like light base), with symbol layers'
`text-field` forced to `["coalesce", ["get","name:he"], ["get","name:en"], ["get","name"]]`.
Tile source lives in the style, never hard-coded in application logic, so a swap is one line.
Maptoolkit is the keyless fallback.

Pin `maplibre-gl@6.15.0` or later — 4.x has no bidi and renders Hebrew reversed.

## Consequences

Depends on a volunteer-run tile service with no SLA; the documented fallback is the
mitigation. The dark theme uses a CSS filter over a light base in v1 — a real dark style is
deferred.
