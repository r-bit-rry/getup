# ADR-0008: Everything is public, including gated-community links

- **Status:** Accepted
- **Date:** 2026-10-18
- **Supersedes:** —
- **Superseded by:** —
- **Confirmed:** 2026-10-23 — the repo and the site are public; intake is guarded on `author_association`.

## Context

GitHub Pages on the Free tier requires a public repository, and the published site is
public regardless of repository visibility. Genuinely private Pages requires an Enterprise
Cloud organisation. A public repo also means public issues, indexable, writable by anyone.

## Decision

Publish the ticket link, or the community link for events that require joining a group.
These communities are gated for vetting, not private — they have thousands of members and
joining is a step towards attending, not a secret.

Accept public contributions via issues and pull requests; guard processing on
`author_association` in {OWNER, MEMBER}.

## Consequences

Nothing rendered can ever be made private without re-hosting. If a genuinely private
signal is ever needed, it must not be rendered at all — the portal would show a flag only.
