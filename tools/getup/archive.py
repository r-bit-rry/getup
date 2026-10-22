"""The 90-day roll into one compressed member per month. A corrupt day is warned about and kept."""

import json
import logging
import os
import re
from datetime import date, timedelta

from . import write

log = logging.getLogger('getup')

RETENTION_DAYS = 90
MONTH_FILE = re.compile(r'^(\d{4}-\d{2})\.json\.(?:zst|xz)$')


def codec():
    """zstd when CPython was built with it, else lzma; the suffix always matches the codec."""
    try:
        from compression import zstd
        return 'zstd', '.zst', zstd.compress, zstd.decompress
    except ImportError:
        pass
    try:
        from compression import lzma as modern
        return 'lzma', '.xz', modern.compress, modern.decompress
    except ImportError:
        import lzma as legacy
        return 'lzma', '.xz', legacy.compress, legacy.decompress


def compress(data: bytes) -> bytes:
    return codec()[2](data)


def decompress(data: bytes) -> bytes:
    return codec()[3](data)


def suffix() -> str:
    return codec()[1]


def _month_path(root: str, month: str, fmt: str) -> str:
    return os.path.join(root, 'archive', f'{month}.json{fmt}')


def month_file(root: str, month: str) -> str:
    return _month_path(root, month, suffix())


def archive_months(root: str) -> list[str]:
    """Every month with a member on disk, sorted. Enumerates names; never decompresses."""
    try:
        names = os.listdir(os.path.join(root, 'archive'))
    except OSError:
        return []
    return sorted({match.group(1) for name in names if (match := MONTH_FILE.match(name))})


def roll(root: str, today: str, *, codec_override=None) -> list[str]:
    """Move days older than the retention window into their month's member; returns the days moved."""
    _, fmt, compress_data, decompress_data = codec_override or codec()
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
        path = _month_path(root, month, fmt)
        payload = {}
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    payload = json.loads(decompress_data(f.read()))
            except Exception as exc:    # replacing a month we cannot read would lose it
                log.warning('getup: archive %s unreadable, month skipped: %s', month, exc)
                continue
            if not isinstance(payload, dict):
                log.warning('getup: archive %s is not an object, month skipped', month)
                continue
        payload.update(by_month[month])
        write.write_bytes(path, compress_data(write.dumps(payload).encode('utf-8')))
        for day in sorted(by_month[month]):
            os.remove(write.date_file(root, day))
            archived.append(day)
    return archived
