# Operations: the daily run on the phone

One script, one cron-like trigger: `scripts/daily.sh`. It runs `intake` → `build` →
`coverage` → `archive`, then commits and pushes whatever changed under `data/`,
`venue/` and `prefs.json`. It is POSIX `sh`, no dependencies beyond `git` and the
Python that is already on the phone.

Intake runs first so a new issue is placed by the build that follows it, on the
same day.

## Termux

```sh
pkg install python git openssh
```

No pip packages: the pipeline is standard library only. `scripts/daily.sh` is in
the repo; call it by path, no install step.

## Environment

Credentials live in one file, readable only by the owner:

```sh
mkdir -p ~/.config/getup
cat > ~/.config/getup/env.sh <<'EOF'
export GETUP_REPO=owner/name
export GETUP_GITHUB_TOKEN=...
export GETUP_LOG=$HOME/getup-daily.log
EOF
chmod 700 ~/.config/getup
chmod 600 ~/.config/getup/env.sh
```

`GETUP_REPO` is `owner/name`. `GETUP_GITHUB_TOKEN` must be able to read and write
issues and labels on that repo (`gh auth token` prints one). `GETUP_LOG` is
optional; when set, every line the script prints is also appended there.

Optional: `GETUP_ROOT` (default: the repo containing the script), `GETUP_PYTHON`
(default `python3`).

## Schedule

`termux-job-scheduler` is the preferred trigger: Android may kill a `crond` in
the background, and the job scheduler survives reboots with `--persisted`.

```sh
cat > ~/bin/getup-daily <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
. "$HOME/.config/getup/env.sh"
termux-wake-lock
sh "$HOME/repos/event-finder-getup-site/scripts/daily.sh"
termux-wake-unlock
EOF
chmod 700 ~/bin/getup-daily

termux-job-scheduler --script "$HOME/bin/getup-daily" --period-ms 86400000 --persisted true
termux-job-scheduler --list
```

`termux-wake-lock` holds a partial wake lock for the run; without it Doze can
freeze the process mid-build. Battery optimisation must also exempt Termux
(Android Settings → Apps → Termux → Battery → Unrestricted). Both are required:
the wake lock covers the run, the exemption covers the trigger.

Cron fallback, if the job scheduler is not available:

```sh
pkg install cronie
crond
crontab -e        # then add:
# 17 6 * * * . "$HOME/.config/getup/env.sh" && sh "$HOME/repos/event-finder-getup-site/scripts/daily.sh"
```

A cron entry has almost no `PATH`; sourcing the env file and calling `sh` by an
absolute path (as above) avoids both the missing token and the missing `git`.

## Offline

There is no separate ping. The first thing that touches the network is `intake`,
and it fails closed: no HTTP means exit `5`, one `failed at intake` line, and no
commit. Nothing is half-pushed.

A run that starts online and loses the network mid-poll is the one partial case:
`intake` treats a per-issue failure as success (`0`), so drafts already written
stay in the working tree, and the `build` that follows fails on its own sources
and stops the run before any commit. Those drafts are picked up by the next
successful run; re-running is safe.

## Exit codes and the log

| Code | Meaning | What the script does |
|---|---|---|
| `0` | all four steps ran; committed and pushed, or nothing to commit | done |
| `3` from `coverage` only | a major venue went quiet for 14 days | reported, run continues |
| `1` | a step failed (build `2`, archive, git, push) | stops, no commit or no push |
| `5` | preflight, GitHub API/auth, or a corrupt state file | stops before writing |

Every line starts with a UTC timestamp and `daily:`; each step contributes at
least one (`intake: exit 0`, `build: exit 0`, `sources: leaan: ok, popit: ok,
biluim: ok`, `coverage: exit 3`, `archive: exit 0`), and a failing step's output
follows, indented. The last line of a failed run names the step: `failed at push
(exit 1): push failed after 3 attempts`.

Nothing changed looks like:

```
... daily: commit: nothing changed under data/, venue/, prefs.json
```

and the process exits `0`. A failure always has a `failed at <step>` line and a
non-zero exit; an empty or missing log with a zero exit means the trigger never
fired, not that the run succeeded.

## Idempotency

Re-running is safe and is the recovery procedure. `intake` only reads issues that
still carry `intake` (not `processed`), `build` is a pure function of captures +
drafts + registry, `coverage` only reads, and `archive` moves nothing on a second
run. `git commit` is skipped when the staged diff is empty.

The one exception: `build` stamps `generated_at` in `data/index.json` on every
run, so every run stages `data/index.json` and therefore commits. A day with no
news commits a timestamp-only diff. That is accepted: it keeps the commit as a
heartbeat, and it makes "the scheduler stopped" visible as a gap in the log.

## Manual recovery

```sh
sh ~/repos/event-finder-getup-site/scripts/daily.sh
```

Re-run after any failure. If `push` failed, the commit is local and the next run
commits nothing (no staged diff) and pushes it. If a run was killed mid-build,
the working tree may hold a half-written day file; the next `build` rewrites it.
To inspect without committing, `--dry-run` runs all four steps and prints the
paths it would stage.

`--dry-run` does not stage, commit or push, and does not clean the working tree:
a killed run leaves its files exactly where they were.
