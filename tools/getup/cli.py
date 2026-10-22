"""The command line: build, pending, labels, coverage, archive."""

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime

from . import (archive, build, classify, coverage, dedup, github, intake, normalize, scan,
               venues, write)

SOURCES = ('leaan', 'popit', 'biluim')
EXIT_CODES = ('exit codes: 0 ok — a per-issue intake failure is still 0, 1 bad arguments, '
              '2 a source failed/partial or a bad --sources/--today value, '
              '3 coverage missed a major venue, 4 tz data missing, '
              '5 intake: GitHub API or token failure, or a corrupt '
              'prefs.json/venues.json/human.json')
log = logging.getLogger('getup')


def _shared(sub, scanning=False):
    sub.add_argument('--root', default='.')
    sub.add_argument('--today')
    if scanning:
        sub.add_argument('--sources', nargs='+', default=list(SOURCES))
        sub.add_argument('--from-dir')


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='getup', epilog=EXIT_CODES)
    subs = parser.add_subparsers(dest='command', required=True)
    _shared(subs.add_parser('build'), scanning=True)
    _shared(subs.add_parser('pending'), scanning=True)
    labels = subs.add_parser('labels')
    labels.add_argument('--root', default='.')
    labels.add_argument('--labels', required=True)
    _shared(subs.add_parser('coverage'))
    _shared(subs.add_parser('archive'))
    _shared(subs.add_parser('intake', epilog=EXIT_CODES))   # its own exit codes on its own help
    return parser


def _today(args) -> str:
    if not args.today:
        return datetime.now(normalize.tz()).date().isoformat()
    try:
        date.fromisoformat(args.today)
    except ValueError as exc:
        raise ValueError(f'--today {args.today}: {exc}') from exc
    return args.today


def _drafts(args):
    names = list(args.sources)
    if args.from_dir is None:
        return scan.scan(names)
    return scan.scan_from_dir(names, args.from_dir)


def _build(args) -> int:
    out = build.run(args.root, _today(args), sources=args.sources, from_dir=args.from_dir)
    for name, source in out['sources'].items():
        print(f'{name}: {source["status"]} {source["count"]}')
    for source in out['sources'].values():
        if source['status'] != 'ok':
            for line in source['failures']:
                print(line, file=sys.stderr)
    print(f'written {len(out["written"])} days, pruned {out["pruned"]}, '
          f'dropped_no_venue {out["dropped_no_venue"]}, unpinned {out["unpinned"]}')
    return 0 if all(s['status'] == 'ok' for s in out['sources'].values()) else 2


def _pending(args) -> int:
    drafts, _, failures, status = _drafts(args)
    for line in failures:
        print(line, file=sys.stderr)
    registry = venues.load(args.root)          # in memory only: no geocode, no save
    kept, _ = build.place(registry, drafts)
    records = [rec for rec in (normalize.record(draft) for draft in kept) if rec is not None]
    batch = classify.pending(dedup.merge(records), classify.load(args.root))
    path = os.path.join(args.root, 'build', 'labels.pending.jsonl')
    write.write_bytes(path, ''.join(json.dumps(p, ensure_ascii=False) + '\n'
                                    for p in batch).encode('utf-8'))
    print(f'{len(batch)} titles pending from {len(records)} records: {path}')
    return 2 if status and set(status.values()) == {'failed'} else 0


def _labels(args) -> int:
    replies = []
    try:
        with open(args.labels, encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    replies.append(json.loads(line))
    except (OSError, ValueError) as exc:
        print(f'getup: {args.labels}: {exc}', file=sys.stderr)
        return 1
    merged = classify.merge(classify.load(args.root), replies)
    classify.save(args.root, merged)
    print(f'{len(merged)} labels cached')
    return 0


def _coverage(args) -> int:
    out = coverage.report(args.root, _today(args))
    missed = out['missed']
    print(f'coverage: {out["checked"]} major venues checked, {len(missed)} missed')
    for miss in missed:
        print(f'missed: {miss["venue_id"]} {miss["name"]}')
    return 3 if missed else 0


def _archive(args) -> int:
    moved = archive.roll(args.root, _today(args))
    print(f'archived {len(moved)} days: {" ".join(moved)}' if moved else 'archived 0 days')
    return 0


def _intake(args) -> int:
    today = _today(args)
    try:
        intake.check_state(args.root)          # before any network: a corrupt store never polls
        client = intake.client_from_env()      # resolved at call time, never at import
        rows = intake.poll(args.root, client=client, today=today)
    except (github.GithubError, ValueError) as exc:
        print(f'getup: {exc}', file=sys.stderr)
        return 5
    for row in rows:                           # a failed issue is one line, not this command's failure
        line = f'#{row["number"]}: {row["result"]}'
        if row['problems']:
            line += ' — ' + ' · '.join(row['problems'])
        print(line)
    return 0


def main(argv: list) -> int:
    try:
        args = _parser().parse_args(list(argv))
    except SystemExit as exc:                  # argparse owns --help and the usage errors
        return 0 if exc.code == 0 else 1
    handler = {'build': _build, 'pending': _pending, 'labels': _labels,
               'coverage': _coverage, 'archive': _archive, 'intake': _intake}[args.command]
    try:
        return handler(args)
    except ValueError as exc:                  # --sources nope, a bad --today
        print(f'getup: {exc}', file=sys.stderr)
        return 2
    except RuntimeError as exc:
        if 'tz data' not in str(exc):
            raise
        print(f'{exc}', file=sys.stderr)
        return 4
