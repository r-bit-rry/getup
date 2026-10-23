"""Canonical JSON bytes and the day-file layout. The only module that dumps JSON."""

import json
import os
import re
from datetime import datetime, timezone

DAY_FILE = re.compile(r'^\d{4}-\d{2}-\d{2}\.json$')
INTERNAL_KEYS = frozenset({'tags'})


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + '\n'


def write_bytes(path: str, data: bytes) -> bool:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    try:
        with open(path, 'rb') as f:
            if f.read() == data:
                return False
    except OSError:
        pass
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, path)
    return True


def write_json(path: str, obj) -> bool:
    return write_bytes(path, dumps(obj).encode('utf-8'))


def read_json(path: str, default=None):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def read_json_strict(path: str):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError) as exc:
        raise ValueError(f'{path}: {exc}') from exc


def date_file(root, day) -> str:
    return os.path.join(root, 'data', f'{day}.json')


def index_file(root) -> str:
    return os.path.join(root, 'data', 'index.json')


def labels_file(root) -> str:
    return os.path.join(root, 'data', 'labels.json')


def data_files(dirpath: str) -> list[str]:
    try:
        names = os.listdir(dirpath)
    except OSError:
        return []
    return sorted(name[:-5] for name in names if DAY_FILE.match(name))


def write_days(root: str, by_day: dict[str, list]) -> list[str]:
    written = []
    for day in sorted(by_day):
        records = [{k: v for k, v in rec.items() if k not in INTERNAL_KEYS}
                   for rec in by_day[day]]
        if write_json(date_file(root, day), records):
            written.append(day)
    return written


def prune_future(root: str, keep: set[str], today: str) -> list[str]:
    removed = []
    for day in data_files(os.path.join(root, 'data')):
        if day > today and day not in keep:
            os.remove(date_file(root, day))
            removed.append(day)
    return removed


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
