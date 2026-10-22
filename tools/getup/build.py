"""The daily run: scan, place, normalize, dedupe, classify, derive, write, prune, index."""

import json
import logging
import os

from . import (archive, classify, coverage, dedup, derive, geo, human, manifest, normalize,
               scan, venues, write)

log = logging.getLogger('getup')

SERVE_DAYS = normalize.SERVE_DAYS


def _merge_day(seen: dict, records) -> None:
    for rec in records if isinstance(records, list) else []:
        if not isinstance(rec, dict):
            continue
        event_id, mark = rec.get('id'), rec.get('seen')
        if not isinstance(event_id, str) or not isinstance(mark, dict):
            continue
        first, last = mark.get('first'), mark.get('last')
        if not isinstance(first, str) or not isinstance(last, str):
            continue
        prior = seen.get(event_id)
        seen[event_id] = {'first': min(first, prior['first']) if prior else first,
                          'last': max(last, prior['last']) if prior else last}


def _archive_month(root, month) -> dict:
    path = archive.month_file(root, month)
    try:
        with open(path, 'rb') as f:
            payload = json.loads(archive.decompress(f.read(), os.path.splitext(path)[1]))
    except Exception as exc:
        log.warning('getup: history skipped unreadable month %s: %s', month, exc)
        return {}
    return payload if isinstance(payload, dict) else {}


def _day_records(root, day) -> list:
    records = write.read_json(write.date_file(root, day), None)
    if not isinstance(records, list):
        log.warning('getup: history skipped unreadable day %s', day)
        return []
    return records


def history(root) -> dict:
    """Every event id's first and last sighting, from day files and archived months alike."""
    seen = {}
    for day in write.data_files(os.path.join(root, 'data')):
        _merge_day(seen, _day_records(root, day))
    for month in archive.archive_months(root):
        payload = _archive_month(root, month)
        for day in sorted(payload):
            _merge_day(seen, payload[day])
    return {'seen': seen}


def window(records, today) -> list:
    """The served 30 dates, the same ones the write covers."""
    days = set(normalize.horizon(today))
    return [rec for rec in records if isinstance(rec, dict) and rec.get('day') in days]


def _labels(root, labels_path) -> dict:
    """``data/labels.json``, or an alternate cache the caller names; this module never writes one."""
    if labels_path is None:
        return classify.load(root)
    data = write.read_json(labels_path, {})
    if not isinstance(data, dict):
        return {}
    return {k: classify.sanitize(v) for k, v in data.items()
            if isinstance(k, str) and classify.KEY_RE.match(k)}


def _tally(status, records, failures) -> tuple:
    """Survivor counts plus one line naming every source left with nothing."""
    counts, states = scan.tally(status, records, failures)
    for name, state in states.items():
        if state == 'failed' and not any(f.startswith(f'{name}:') for f in failures):
            failures.append(f'{name}: no records survived normalization')
    return counts, states


def place(registry: dict, drafts) -> tuple:
    """Resolve each draft's venue in memory; a draft with no venue string is dropped and counted."""
    kept, dropped = [], 0
    for draft in drafts:
        venue_id = venues.resolve(registry, draft.get('venue'), draft.get('city'))
        if venue_id is None:
            dropped += 1
            log.warning('getup: dropped %s %s: no venue', draft.get('source'), draft.get('source_id'))
            continue
        draft['venue_id'] = venue_id
        kept.append(draft)
    return kept, dropped


def _pinned(venue) -> bool:
    return (venue.get('lat') is not None and venue.get('lon') is not None
            and venue.get('drive_min') is not None)


def _normalized(registry: dict, drafts) -> list:
    """Placed drafts -> records, with the point of this run's registry, never of ingestion."""
    out = []
    for draft in drafts:
        venue_id = draft['venue_id']
        venue = registry.get(venue_id) or {}
        draft['city'] = venues.city_of(registry, venue_id, draft.get('city'))
        draft['lat'], draft['lon'] = venue.get('lat'), venue.get('lon')
        draft['drive_min'] = venue.get('drive_min')
        draft['coords_source'] = venue.get('coords_source')
        record = normalize.record(draft)
        if record is not None:
            out.append(record)
    return out


def run(root, today, *, sources=('leaan', 'popit', 'biluim'), from_dir=None,
        labels_path=None, fetch=scan.fetch_text, now=None) -> dict:
    names = list(sources)
    if from_dir is None:
        drafts, _, failures, status = scan.scan(names, fetch=fetch)
    else:
        drafts, _, failures, status = scan.scan_from_dir(names, from_dir)

    registry = venues.load(root)
    kept, dropped_no_venue = place(registry, drafts)
    # Canonical human drafts are re-placed every run: a new venue is provisioned and pinned before
    # the records are built, so a correction gains its minutes as the registry learns them.
    human_kept, _ = place(registry, human.records(human.load(root)))

    if from_dir is None:
        geo.fill(registry, fetch=fetch)          # a geocode failure is not fatal
    geo.seed(registry)                          # offline too, so a captured city always has minutes

    records = _normalized(registry, kept)
    human_records = _normalized(registry, human_kept)

    counts, states = _tally(status, records, failures)   # before dedup: an absorbed row still counts
    records = classify.apply(dedup.merge(records + human_records), _labels(root, labels_path))
    touring = derive.touring(records)           # the whole payload, not the served subset
    served = derive.signals(window(records, today), touring=touring, registry=registry)

    for record in records:                      # scanned today, even when its next event is far out
        # A manual post is not a scan: one human row must not mask a broken adapter for a major venue.
        if (record.get('source') or {}).get('class') == 'human':
            continue
        venue = registry.get(record['venue_id'])
        if isinstance(venue, dict):
            venue['seen_last'] = today
    venues.save(root, registry)

    prior = history(root)['seen']
    for record in served:
        first = (prior.get(record['id']) or {}).get('first')
        record['seen'] = {'first': min(first, today) if first else today, 'last': today}

    by_day = {day: [] for day in normalize.horizon(today)}
    for record in served:
        by_day[record['day']].append(record)
    written = ([] if set(states.values()) == {'failed'}
               else write.write_days(root, by_day))

    pruned = None
    if all(state == 'ok' for state in states.values()):
        pruned = write.prune_future(root, set(by_day), today)
        archive.roll(root, today)

    index_sources = {name: {'status': states[name], 'count': counts[name],
                            'failures': [f for f in failures if f.startswith(f'{name}:')]}
                     for name in status}
    unpinned = sum(1 for record in served
                   if not _pinned(registry.get(record['venue_id']) or {}))
    index = manifest.build_index(generated_at=now or write.utc_now(),
                                 counts=manifest.day_counts(root),
                                 coverage=coverage.report(root, today),
                                 sources=index_sources, dropped_no_venue=dropped_no_venue,
                                 unpinned=unpinned)
    manifest.write_index(root, index)
    return {'written': written, 'pruned': pruned, 'counts': counts, 'sources': index_sources,
            'coverage': index['coverage'], 'dropped_no_venue': dropped_no_venue,
            'unpinned': unpinned}
