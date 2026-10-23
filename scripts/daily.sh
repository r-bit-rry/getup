#!/bin/sh
# The daily run: intake -> build -> coverage -> archive -> commit -> push.
# Exit: 0 nothing to do or all done, 1 a step failed, 5 preflight/API/auth/state.
set -eu

STEP=preflight
CODE=0
OUT=
EXIT_MSG=
TODAY=$(date -u +%Y-%m-%d)
STATUSES=
DRY_RUN=0

usage() {
  cat <<'EOF'
usage: scripts/daily.sh [--dry-run]

intake, build, coverage, archive, then commit data/, venue/ and prefs.json
and push. --dry-run runs the four steps and prints the paths it would stage.

GETUP_REPO and GETUP_GITHUB_TOKEN are required. Optional: GETUP_LOG,
GETUP_PYTHON (default python3), GETUP_ROOT (default this repo).
EOF
}

log() {
  line="$(date -u +%Y-%m-%dT%H:%M:%SZ) daily: $*"
  printf '%s\n' "$line"
  if [ -n "${GETUP_LOG:-}" ]; then printf '%s\n' "$line" >> "$GETUP_LOG"; fi
}

on_exit() {
  code=$?
  if [ "$code" -ne 0 ]; then log "failed at $STEP (exit $code)${EXIT_MSG:+: $EXIT_MSG}"; fi
  exit "$code"
}

# Child output lines are reported one per line, timestamped, so a log holds the whole story.
report() {
  printf '%s\n' "$1" | while IFS= read -r row; do
    if [ -n "$row" ]; then log "  $row"; fi
  done
}

# step <name> <allowed exit codes> <command...>; anything outside <allowed> is fatal.
step() {
  STEP=$1
  allowed=$2
  shift 2
  set +e
  OUT=$(cd "$GETUP_ROOT" && PYTHONPATH="$GETUP_ROOT" "$@" 2>&1)
  CODE=$?
  set -e
  case " $allowed " in
    *" $CODE "*)
      log "$STEP: exit $CODE"
      # Coverage 3 is not fatal but is the point of the step; everything else is noise on success.
      if [ "$CODE" -ne 0 ] && [ -n "$OUT" ]; then report "$OUT"; fi ;;
    *) report "$OUT"; EXIT_MSG="$STEP exited $CODE"; exit "$CODE" ;;
  esac
}

changes() {
  git -C "$GETUP_ROOT" status --porcelain --untracked-files=all -- data venue prefs.json
}

for arg in "$@"; do
  case "$arg" in
    --help|-h) usage; exit 0 ;;
    --dry-run) DRY_RUN=1 ;;
    *) usage >&2; exit 1 ;;
  esac
done

GETUP_ROOT=${GETUP_ROOT:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}
PYTHON=${GETUP_PYTHON:-python3}

# Before anything is read or written: a run without credentials cannot do its first step.
if [ -z "${GETUP_REPO:-}" ] || [ -z "${GETUP_GITHUB_TOKEN:-}" ]; then
  printf 'daily: GETUP_REPO and GETUP_GITHUB_TOKEN must both be set\n' >&2
  exit 5
fi
trap on_exit EXIT

log "start $TODAY (root $GETUP_ROOT)"
step intake 0 "$PYTHON" -m tools.getup intake --root "$GETUP_ROOT"
step build 0 "$PYTHON" -m tools.getup build --root "$GETUP_ROOT"
STATUSES=$(printf '%s\n' "$OUT" | sed -n 's/^\([a-z]*: [a-z]*\) [0-9][0-9]*$/\1/p' | paste -sd ',' - | sed 's/,/, /g')
log "sources: ${STATUSES:-unknown}"
step coverage "0 3" "$PYTHON" -m tools.getup coverage --root "$GETUP_ROOT"
step archive 0 "$PYTHON" -m tools.getup archive --root "$GETUP_ROOT"

STEP=changes
if ! STAGED=$(changes); then EXIT_MSG='git status failed'; exit 1; fi

if [ "$DRY_RUN" -eq 1 ]; then
  log "dry-run: ${TODAY}, no commit and no push"
  if [ -n "$STAGED" ]; then printf '%s\n' "$STAGED" | sed 's/^...//'; fi
  log 'dry-run: done'
  exit 0
fi

if [ -z "$STAGED" ]; then
  log 'commit: nothing changed under data/, venue/, prefs.json'
  exit 0
fi

STEP=commit
log "commit: $TODAY"
git -C "$GETUP_ROOT" add -- data venue prefs.json
if git -C "$GETUP_ROOT" diff --cached --quiet; then
  log 'commit: nothing staged'
  exit 0
fi
git -C "$GETUP_ROOT" commit -m "data: daily run $TODAY" -m "sources: ${STATUSES:-unknown}"

STEP=push
attempt=1
while [ "$attempt" -le 3 ]; do
  if git -C "$GETUP_ROOT" push; then
    log "push: ok on attempt $attempt"
    break
  fi
  if [ "$attempt" -eq 3 ]; then EXIT_MSG='push failed after 3 attempts'; exit 1; fi
  log "push: attempt $attempt failed"
  sleep "$((attempt * 5))"
  attempt=$((attempt + 1))
done
log 'done'
