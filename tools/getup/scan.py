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
        cassette = os.path.join(path, adapters[name].CASSETTE)

        def read(url, _file=cassette):
            with open(_file, encoding='utf-8') as f:
                return f.read()

        found, found_counts, found_failures, found_status = scan(
            [name], fetch=read, adapters=adapters)
        drafts.extend(found)
        counts.update(found_counts)
        failures.extend(found_failures)
        status.update(found_status)
    return drafts, counts, failures, status
