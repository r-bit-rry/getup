# ADR-0001: No build step; vanilla ES modules on GitHub Pages

- **Status:** Accepted
- **Date:** 2026-10-18
- **Supersedes:** —
- **Superseded by:** —

## Context

The site is fed by an agent that commits JSON daily. Any build step (Vite, React,
Tailwind) inserts a CI job between a data update and the page that shows it, adds
`node_modules` and a lockfile to a public repo, and introduces a second failure mode
(build breakage) in the durability path. The concept mockup already proved the design is
achievable in ~28 KB of hand-written HTML/CSS/JS with MapLibre and two fonts as the only
externals.

## Decision

Serve directly from the branch root. No bundler, no framework, no npm. Application code
is vanilla ES modules; styling is hand-written CSS with design tokens. Third-party runtime
code (MapLibre) and fonts are vendored into `assets/`.

Committing JSON is the whole deploy.

## Consequences

Contributors edit HTML/CSS directly rather than components. No shadcn-style component
library. If the app later genuinely needs a component framework, this is superseded by a
new ADR, and the migration is a rewrite of `app.js` only.
