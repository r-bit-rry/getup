# ADR-0009: Hebrew-first, RTL only, no i18n layer

- **Status:** Accepted
- **Date:** 2026-10-18
- **Supersedes:** —
- **Superseded by:** —

## Context

Every source delivers Hebrew titles, venues and descriptions. A language toggle would
translate the chrome while leaving the content Hebrew, which reads worse than consistent
Hebrew. RTL costs almost nothing in this stack: `dir="rtl"`, Tailwind-style logical
properties, and MapLibre's now-native bidi.

## Decision

`<html lang="he" dir="rtl">`. No i18n framework, no locale toggle, no translated strings.
Content is never translated.

Typography must carry Hebrew and Latin in one family — Rubik. Hebrew has no uppercase, so
Latin uppercase micro-label systems do not translate.

## Consequences

Sharing with non-Hebrew speakers is impossible without a later rework. Deferred
deliberately; a future English layer would be a new ADR, not a retrofit.
