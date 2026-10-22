"""Biluim: Tailwind listing cards become aggregator drafts."""

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
URLS = [f'{BASE}/events/tel-aviv']
NUMBER = re.compile(r'\d+')
EVENT = '/events/e/'
VENUE = '/events/venues/'
# HTMLParser never implies an end tag for these, so they must not move the depth.
VOID = frozenset({'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
                  'link', 'meta', 'param', 'source', 'track', 'wbr'})
EMPTY = {'title': None, 'aria': None, 'href': None, 'venue': None,
         'price': None, 'tag': None, 'when': None}


def _tz():
    try:
        return ZoneInfo('Asia/Jerusalem')
    except Exception as exc:
        raise RuntimeError('getup: no tz data for Asia/Jerusalem') from exc


class CardParser(HTMLParser):
    """Collects every article.group card that carries an event link."""

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
        if tag in VOID:
            return
        attrs = dict(attrs)
        classes = (attrs.get('class') or '').split()
        if self._card is None:
            if tag == 'article' and 'group' in classes:
                self._card, self._depth = dict(EMPTY), 0
            return
        self._depth += 1
        if tag == 'article':
            return                                  # a nested article stays part of this card
        if self._field is not None:
            return
        href = attrs.get('href') or ''
        if href.startswith(EVENT):
            self._card['href'] = self._card['href'] or href
            self._card['aria'] = self._card['aria'] or attrs.get('aria-label')
        if tag == 'time' and attrs.get('datetime'):
            self._card['when'] = self._card['when'] or attrs['datetime']
        name = None
        if tag == 'h3' and 'font-extrabold' in classes:
            name = 'title'
        elif tag == 'a' and href.startswith(VENUE):
            name = 'venue'
        elif tag == 'span' and 'truncate' in classes:
            name = 'venue'                          # the map-pin span; the clock row has no truncate
        elif tag == 'span' and 'glass' in classes and 'tabular-nums' in classes:
            name = 'price'
        elif (tag == 'span' and 'glass' in classes and 'rounded-full' in classes
              and 'tabular-nums' not in classes):
            name = 'tag'
        if name:
            self._field, self._field_tag, self._field_depth, self._buffer = (
                name, tag, self._depth, [])

    def handle_data(self, data):
        if self._field is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag):
        if tag in VOID or self._card is None:
            return
        if tag == 'article' and self._depth == 0:
            self.cards.append(self._card)
            self._card, self._field, self._buffer = None, None, []
            return
        if (self._field is not None and tag == self._field_tag
                and self._depth == self._field_depth):
            text = ' '.join(''.join(self._buffer).split())
            self._card[self._field] = self._card[self._field] or text or None
            self._field, self._buffer = None, []
        self._depth -= 1


def _price(text):
    if not text:
        return None, None
    if 'חינם' in text:
        return 0, None
    numbers = NUMBER.findall(text.replace(',', ''))
    if not numbers:
        return None, None
    tail = text.split('עד', 1)
    top = NUMBER.search(tail[1]) if len(tail) == 2 else None
    return int(numbers[0]), int(top.group()) if top else None


def _start(raw):
    if not raw:
        return None
    try:
        moment = datetime.fromisoformat(raw.strip())
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=_tz())
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
            log.warning('biluim: no article.group cards in the page')
        return []
    drafts = []
    for index, card in enumerate(parser.cards):
        title = card['title'] or card['aria']
        start = _start(card['when'])
        if not card['href'] or not title or start is None:
            log.warning('biluim[%d]: dropped, no link, title or start', index)
            continue
        price_from, price_max = _price(card['price'])
        drafts.append({
            'source': NAME,
            'class': CLASS,
            'source_id': card['href'],
            'title': title,
            'venue': card['venue'],
            'city': None,
            'street': None,
            'start': start,
            'end': None,
            'price_from': price_from,
            'price_max': price_max,
            'soldout': None,
            'desc': None,
            'url': urljoin(BASE, card['href']),
            'tags': [card['tag']] if card['tag'] else [],
        })
    return drafts
