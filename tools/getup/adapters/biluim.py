"""Biluim: HTML listing cards become aggregator drafts."""

import logging
import re
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

log = logging.getLogger('getup')

NAME = 'biluim'
CLASS = 'aggregator'
CASSETTE = 'biluim.html'
BASE = 'https://biluim.co.il'
URLS = [f'{BASE}/events']
TZ = ZoneInfo('Asia/Jerusalem')
FIELDS = ('title', 'venue', 'city', 'price', 'desc')
EMPTY = {'title': None, 'href': None, 'venue': None, 'city': None,
         'price': None, 'desc': None, 'when': None}
NUMBER = re.compile(r'\d+')


class CardParser(HTMLParser):
    """Collects every <li class="event"> card and the fields inside it."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cards = []
        self._card = None
        self._depth = 0
        self._field = None
        self._field_tag = None
        self._field_depth = 0
        self._buffer = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get('class') or '').split()
        if self._card is None:
            if tag == 'li' and 'event' in classes:
                self._card, self._depth = dict(EMPTY), 0
            return
        self._depth += 1
        if self._field is not None:
            return
        if attrs.get('href'):
            self._card['href'] = self._card['href'] or attrs['href']
        if tag == 'time' and attrs.get('datetime'):
            self._card['when'] = attrs['datetime']
        name = next((name for name in FIELDS if name in classes), None)
        if name:
            self._field, self._field_tag, self._field_depth, self._buffer = (
                name, tag, self._depth, [])

    def handle_data(self, data):
        if self._field is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag):
        if self._card is None:
            return
        if self._field is not None and tag == self._field_tag and self._depth == self._field_depth:
            text = ' '.join(''.join(self._buffer).split())
            self._card[self._field] = self._card[self._field] or text or None
            self._field = None
        if tag == 'li' and self._depth == 0:
            self.cards.append(self._card)
            self._card = None
            return
        self._depth -= 1


def _price(text):
    if not text:
        return None
    if 'חינם' in text:
        return 0
    found = NUMBER.search(text.replace(',', ''))
    return int(found.group()) if found else None


def _start(raw):
    if not raw:
        return None
    try:
        moment = datetime.fromisoformat(raw.strip())
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=TZ)
    return int(moment.timestamp())


def parse(payload: str) -> list[dict]:
    parser = CardParser()
    try:
        parser.feed(payload)
        parser.close()
    except Exception as exc:
        log.warning('biluim: unreadable HTML: %s', exc)
        return []
    if not parser.cards:
        if payload.strip():
            log.warning('biluim: no <li class="event"> cards in the page')
        return []
    drafts = []
    for index, card in enumerate(parser.cards):
        start = _start(card['when'])
        if not card['title'] or start is None:
            log.warning('biluim[%d]: dropped, no title or start', index)
            continue
        drafts.append({
            'source': NAME,
            'class': CLASS,
            'source_id': card['href'],
            'title': card['title'],
            'venue': card['venue'],
            'city': card['city'],
            'street': None,
            'start': start,
            'end': None,
            'price_from': _price(card['price']),
            'price_max': None,
            'soldout': None,
            'desc': card['desc'],
            'url': urljoin(BASE, card['href']) if card['href'] else None,
            'tags': [],
        })
    return drafts
