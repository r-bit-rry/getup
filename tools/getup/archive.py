"""The 90-day roll into one compressed member per month. A corrupt day is warned about and kept."""

import json
import logging
import os
import re
from datetime import date, timedelta

from . import write

log = logging.getLogger('getup')

RETENTION_DAYS = 90
SUFFIXES = ('.zst', '.xz')
MONTH_FILE = re.compile(r'^(\d{4}-\d{2})\.json\.(?:zst|xz)$')


def _zstd():
    from compression import zstd
    return 'zstd', '.zst', zstd.compress, zstd.decompress


def _lzma():
    try:
        from compression import lzma as modern
    except ImportError:
        import lzma as modern
    return 'lzma', '.xz', modern.compress, modern.decompress


def codec(fmt: str | None = None):
    """The codec a suffix names; without one, what this interpreter prefers."""
    if fmt == '.xz':
        return _lzma()
    if fmt == '.zst':
        return _zstd()
    try:
        return _zstd()
    except ImportError:
        return _lzma()


def compress(data: bytes, fmt: str | None = None) -> bytes:
    return codec(fmt)[2](data)


def decompress(data: bytes, fmt: str | None = None) -> bytes:
    return codec(fmt)[3](data)


def suffix() -> str:
    return codec()[1]


def _month_path(root: str, month: str, fmt: str) -> str:
    return os.path.join(root, 'archive', f'{month}.json{fmt}')


def _members(root: str, month: str) -> list[str]:
    return [_month_path(root, month, fmt) for fmt in SUFFIXES]


def month_file(root: str, month: str) -> str:
    """The member this month already has, whichever suffix it carries; else the current suffix."""
    paths = [_month_path(root, month, suffix()), *_members(root, month)]
    return next((path for path in paths if os.path.exists(path)), paths[0])


def archive_months(root: str) -> list[str]:
    """Every month with a member on disk, sorted. Enumerates names; never decompresses."""
    try:
        names = os.listdir(os.path.join(root, 'archive'))
    except OSError:
        return []
    return sorted({match.group(1) for name in names if (match := MONTH_FILE.match(name))})


def roll(root: str, today: str) -> list[str]:
    """Move days older than the retention window into their month's member; returns the days moved."""
    cutoff = (date.fromisoformat(today) - timedelta(days=RETENTION_DAYS)).isoformat()
    by_month = {}
    for day in write.data_files(os.path.join(root, 'data')):
        if day >= cutoff:
            continue
        try:
            records = write.read_json_strict(write.date_file(root, day))
        except ValueError as exc:       # a corrupt day stays exactly where it is
            log.warning('getup: archive skipped %s: %s', day, exc)
            continue
        by_month.setdefault(day[:7], {})[day] = records

    archived = []
    for month in sorted(by_month):
        target = month_file(root, month)
        payload = {}
        for path in _members(root, month):            # a codec change can leave both suffixes
            if not os.path.exists(path):
                continue
            try:
                with open(path, 'rb') as f:
                    loaded = json.loads(decompress(f.read(), os.path.splitext(path)[1]))
            except Exception as exc:    # replacing a month we cannot read would lose it
                log.warning('getup: archive %s unreadable, month skipped: %s', month, exc)
                payload = None
                break
            if not isinstance(loaded, dict):
                log.warning('getup: archive %s is not an object, month skipped', month)
                payload = None
                break
            payload.update(loaded)
        if payload is None:
            continue
        payload.update(by_month[month])
        write.write_bytes(target, compress(write.dumps(payload).encode('utf-8'),
                                           os.path.splitext(target)[1]))
        for path in _members(root, month):            # only once the merged member is on disk
            if path != target and os.path.exists(path):
                os.remove(path)
        for day in sorted(by_month[month]):
            os.remove(write.date_file(root, day))
            archived.append(day)
    return archived
