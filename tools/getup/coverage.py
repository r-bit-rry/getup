"""The coverage alarm: a major venue with no recent sighting, never an empty day."""

import json
import logging
import os
from datetime import date, timedelta

from . import archive, venues, write

log = logging.getLogger('getup')

LOOKBACK_DAYS = 14


def last_seen_by_venue(records) -> dict:
    """Venue id -> the latest ``seen.last`` across its records; records without one are ignored."""
    latest = {}
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, dict):
            continue
        venue_id = record.get('venue_id')
        seen = record.get('seen')
        last = seen.get('last') if isinstance(seen, dict) else None
        if isinstance(venue_id, str) and isinstance(last, str) and last > latest.get(venue_id, ''):
            latest[venue_id] = last
    return latest


def check(registry, records, today) -> dict:
    """Every major venue whose latest sighting is older than the lookback, sorted by name."""
    cutoff = (date.fromisoformat(today) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    latest = last_seen_by_venue(records)
    majors = [(venue_id, venue) for venue_id, venue in (registry or {}).items()
              if isinstance(venue, dict) and venue.get('tier') == 'major']
    missed = [{'venue_id': venue_id, 'name': venue.get('name') or ''}
              for venue_id, venue in majors if latest.get(venue_id, '') < cutoff]
    return {'checked': len(majors), 'missed': sorted(missed, key=lambda m: m['name'])}


def _day_records(root, day) -> list:
    records = write.read_json(write.date_file(root, day), None)
    if not isinstance(records, list):
        log.warning('getup: coverage skipped unreadable day %s', day)
        return []
    return records


def _archive_records(root, month) -> list:
    path = archive.month_file(root, month)
    try:
        with open(path, 'rb') as f:
            payload = json.loads(archive.decompress(f.read(), os.path.splitext(path)[1]))
    except Exception as exc:
        log.warning('getup: coverage skipped unreadable month %s: %s', month, exc)
        return []
    if not isinstance(payload, dict):
        log.warning('getup: coverage skipped %s: not an object', month)
        return []
    return [rec for day in sorted(payload) for rec in (payload[day] or [])]


def report(root, today) -> dict:
    """The committed state: every day file and every archived day, checked against sightings."""
    records = []
    for day in write.data_files(os.path.join(root, 'data')):
        records.extend(_day_records(root, day))
    for month in archive.archive_months(root):
        records.extend(_archive_records(root, month))
    return check(venues.load(root), records, today)
