# ADR-0014: One shell script is the whole ops layer; no CI, no in-repo scheduler

- **Status:** Accepted
- **Date:** 2026-10-23
- **Supersedes:** —
- **Superseded by:** —

## Context

The daily run is `intake` → `build` → `coverage` → `archive`, then a commit and a push.
The host is an Android phone on Termux, where the pipeline already runs with stdlib
Python and `git` and nothing else. GitHub Actions would put the work on a runner that
cannot hold the venue registry cache or the log, and would add a workflow file to a repo
whose contract is that committing JSON is the deploy (ADR-0001). Any scheduler committed
here would be a second thing to keep alive, invisible from the log.

## Decision

`scripts/daily.sh` — POSIX `sh`, no dependencies beyond `git` and the phone's Python — is
the entire ops layer. It runs the four steps, stages only `data/`, `venue/` and
`prefs.json`, commits when the staged diff is non-empty, and pushes. `--dry-run` runs the
same steps and prints what it would stage. Every line is timestamped and names its step;
a failure stops the run with `failed at <step>` and a non-zero exit.

No GitHub Actions, no webhook, no scheduler in the repository. The trigger lives on the
host (`termux-job-scheduler`, cron as fallback) and is documented in
`docs/operations.md`.

## Consequences

The run is idempotent, so re-running is the recovery procedure and a killed run is fixed
by the next one. Deployment honesty is a consequence of branch state, not of a workflow
badge. The daily schedule is host work nobody has installed yet: until it is, the site
only changes when someone runs the script. A stalled schedule shows up as a stale
`generated_at` in the footer and a gap in the log, which is the intended signal.
