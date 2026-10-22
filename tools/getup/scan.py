"""Adapter transport, per-source counts and failure reporting."""

import logging
import os
import urllib.request

from .adapters import ADAPTERS

log = logging.getLogger('getup')


class FetchError(Exception):
    pass


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={'User-Agent': 'getup/1.0 (+repo url)'})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read().decode('utf-8')
    except Exception as exc:
        raise FetchError(f'{url}: {exc}') from exc


def _resolve(names, adapters):
    unknown = [name for name in names if name not in adapters]
    if unknown:
        raise ValueError(f'unknown source: {", ".join(unknown)}')


def scan(names: list[str], *, fetch=fetch_text, adapters=ADAPTERS):
    _resolve(names, adapters)
    drafts, counts, failures, status = [], {}, [], {}
    for name in names:
        adapter = adapters[name]
        urls = list(adapter.URLS)
        found, dead, broken = [], 0, False
        for url in urls:
            try:
                payload = fetch(url)
            except Exception as exc:
                dead += 1
                failures.append(f'{name}: {url}: {exc}')
                continue
            try:
                found.extend(adapter.parse(payload))
            except Exception as exc:
                broken = True
                failures.append(f'{name}: {url}: {exc}')
        counts[name] = len(found)
        drafts.extend(found)
        if not found:
            status[name] = 'failed'
            if not dead and not broken:
                failures.append(f'{name}: no events parsed')
        elif dead or broken:
            status[name] = 'partial'
        else:
            status[name] = 'ok'
    return drafts, counts, failures, status


def scan_from_dir(names: list[str], path: str, *, adapters=ADAPTERS):
    _resolve(names, adapters)
    drafts, counts, failures, status = [], {}, [], {}
    for name in names:
        file = os.path.join(path, adapters[name].CASSETTE)
        try:
            with open(file, encoding='utf-8') as f:
                payload = f.read()
        except OSError as exc:
            counts[name] = 0
            status[name] = 'failed'
            failures.append(f'{name}: {file}: {exc}')
            continue
        broken = False
        try:
            found = adapters[name].parse(payload)
        except Exception as exc:
            found, broken = [], True
            failures.append(f'{name}: {file}: {exc}')
        counts[name] = len(found)
        drafts.extend(found)
        if found:
            status[name] = 'ok'
        else:
            status[name] = 'failed'
            if not broken:
                failures.append(f'{name}: no events parsed')
    return drafts, counts, failures, status
