"""Leaan: the __NEXT_DATA__ event list becomes ticketing drafts."""

import json
import logging
import re

log = logging.getLogger('getup')

NAME = 'leaan'
CLASS = 'ticketing'
CASSETTE = 'leaan-events.json'
URLS = [
    'https://www.leaan.co.il/category/%D7%9E%D7%95%D7%96%D7%99%D7%A7%D7%94',
    'https://www.leaan.co.il/category/%D7%91%D7%99%D7%93%D7%95%D7%A8-%D7%95%D7%A1%D7%98%D7%A0%D7%93%D7%90%D7%A4',
    'https://www.leaan.co.il/category/%D7%94%D7%A6%D7%92%D7%95%D7%AA-%D7%95%D7%94%D7%A8%D7%A6%D7%90%D7%95%D7%AA',
]
SCRIPT = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
SHAPE_WARNING = 'leaan: no event list at pageData.events'


def extract_next_data(html: str) -> dict:
    match = SCRIPT.search(html)
    if not match:
        raise ValueError('no __NEXT_DATA__ script tag')
    return json.loads(match.group(1))


def _events(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, str):
        try:
            if payload.lstrip().startswith('<'):
                payload = extract_next_data(payload)
            else:
                payload = json.loads(payload)
        except ValueError:
            return None
        return _events(payload)
    if isinstance(payload, dict):
        node = payload
        for key in ('props', 'pageProps', 'initialState', 'pageData'):
            node = node.get(key) if isinstance(node, dict) else None
        events = node.get('events') if isinstance(node, dict) else None
        return events if isinstance(events, list) else None
    return None


def _categories(event) -> list[str]:
    categories = event.get('categories')
    if isinstance(categories, dict):
        return [c['category_name'] for _, c in sorted(categories.items())
                if isinstance(c, dict) and c.get('category_name')]
    return list(categories) if isinstance(categories, list) else []


def _first(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _draft(event) -> dict:
    # Live pages still carry the raw API keys; the committed capture is pre-flattened.
    location = event.get('location') if isinstance(event.get('location'), dict) else {}
    event_id = event.get('event_id')
    price = _first(event.get('price'), event.get('starting_price'))
    multi = _first(event.get('multi_price'), event.get('has_multiple_prices'))
    return {
        'source': NAME,
        'class': CLASS,
        'source_id': event_id,
        'title': _first(event.get('title'), event.get('event_name')),
        'venue': _first(event.get('venue'), location.get('name')),
        'city': _first(event.get('city'), location.get('city')),
        'street': _first(event.get('street'), location.get('street')),
        'start': _first(event.get('start'), event.get('event_start')),
        'end': _first(event.get('end'), event.get('event_end')),
        'price_from': price,
        'price_max': None if multi else price,
        'soldout': _first(event.get('soldout'), event.get('is_soldout')),
        'desc': _first(event.get('desc'), event.get('description')),
        'url': _first(event.get('url'),
                      f'https://www.leaan.co.il/event/{event_id}' if event_id else None),
        'tags': _categories(event),
    }


def parse(payload) -> list[dict]:
    events = _events(payload)
    if events is None:
        log.warning(SHAPE_WARNING)
        return []
    drafts = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            log.warning('leaan[%d]: not an object in pageData.events', index)
            continue
        draft = _draft(event)
        if not draft['title'] or draft['start'] is None:
            log.warning('leaan[%d]: dropped, no title or start', index)
            continue
        drafts.append(draft)
    return drafts
