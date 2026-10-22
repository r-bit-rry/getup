"""``data/index.json``: the only owner of the manifest the client reads first."""

import logging
import os

from . import write

log = logging.getLogger('getup')


def day_counts(root) -> dict:
    """Date -> record count for every readable day file on disk; an unreadable one is omitted."""
    counts = {}
    for day in write.data_files(os.path.join(root, 'data')):
        records = write.read_json(write.date_file(root, day), None)
        if isinstance(records, list):
            counts[day] = len(records)
        else:
            log.warning('getup: index skipped unreadable day %s', day)
    return counts


def build_index(*, generated_at, counts, coverage, sources, dropped_no_venue, unpinned) -> dict:
    counts = counts if isinstance(counts, dict) else {}
    return {
        'generated_at': generated_at,
        'dates': [{'date': day, 'count': counts[day]} for day in sorted(counts)],
        'coverage': coverage if isinstance(coverage, dict) else {},
        'sources': sources if isinstance(sources, dict) else {},
        'dropped_no_venue': dropped_no_venue,
        'unpinned': unpinned,
    }


def write_index(root, index) -> bool:
    return write.write_json(write.index_file(root), index)
