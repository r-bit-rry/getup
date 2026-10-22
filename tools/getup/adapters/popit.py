"""Popit: Hebrew RSS prose, a place hint and a title suffix become nightlife drafts."""

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

log = logging.getLogger('getup')

NAME = 'popit'
CLASS = 'nightlife'
CASSETTE = 'popit.xml'
URLS = ['https://popit.events/feed.xml']
UNKNOWN = 'מיקום לא ידוע'

MONTHS = {'ינואר': 1, 'פברואר': 2, 'מרץ': 3, 'אפריל': 4, 'מאי': 5, 'יוני': 6,
          'יולי': 7, 'אוגוסט': 8, 'ספטמבר': 9, 'אוקטובר': 10, 'נובמבר': 11, 'דצמבר': 12}

# A leading ב glued to a word ("ב-21", "בנמל") but not the ב inside one ("מסיבת").
BET = r'(?<![א-תA-Za-z])ב-?'
WHEN = re.compile(BET + r'(\d{1,2})\s+ב(' + '|'.join(MONTHS) + ')')
# "בשעה 14:00", "פתיחת שערים ב-23:00", "מהשעה 14:00": the first clock in the prose is the start.
CLOCK = re.compile(r'(?<!\d)(\d{1,2}):(\d{2})(?!\d)')
BET_WORD = re.compile(BET)
# The venue phrase follows "…היא מסיבת <style>"; a ב inside the event name before it is not the venue.
FETE = re.compile(r'היא מסיב(?:ה|ת)')

# The English suffixes the feed publishes in titles; a city is not a venue.
PLACE_FIX = {
    'Tel Aviv Port': ('נמל תל אביב', 'תל אביב'),
    'Tel Aviv-Yafo': (None, 'תל אביב'),
    'Petah Tikva': (None, 'פתח תקווה'),
    'Rishon LeZion': (None, 'ראשון לציון'),
    'Israel': (None, None),
    'HaSharon': (None, None),
}


def _tz():
    try:
        return ZoneInfo('Asia/Jerusalem')
    except Exception as exc:
        raise RuntimeError('getup: no tz data for Asia/Jerusalem') from exc


def parse_hebrew_when(text: str, published: datetime) -> int | None:
    """Local unix seconds from "ב-14 בנובמבר בשעה 14:00", or None when the prose gives no date or no clock."""
    match = WHEN.search(text)
    if not match:
        return None
    clock = next((c for c in CLOCK.finditer(text)
                  if int(c.group(1)) < 24 and int(c.group(2)) < 60), None)
    if not clock:
        return None
    hour, minute = int(clock.group(1)), int(clock.group(2))
    month = MONTHS[match.group(2)]
    year = published.year
    if published.month - month >= 6:            # December prose about a January party
        year += 1
    try:
        return int(datetime(year, month, int(match.group(1)), hour, minute, tzinfo=_tz()).timestamp())
    except ValueError:
        return None


def _place_from_description(text: str) -> tuple[str | None, str | None]:
    match = WHEN.search(text)
    if not match:
        return None
    head = text[:match.start()].rstrip(' ,')
    parts = [part.strip() for part in head.split(',')]
    if len(parts) < 2:
        return None
    clause = parts[-2]
    phrase = FETE.search(clause)
    bets = list(BET_WORD.finditer(clause, phrase.end() if phrase else 0))
    if not bets:
        return None
    venue, city = clause[bets[0].end():].strip(), parts[-1]
    if city and any(ch.isdigit() for ch in city):    # 2254 writes the street into the city slot
        city = None
    return (venue, city) if venue else None


def place_from_title(title: str) -> tuple[str | None, str | None]:
    """The text after the last em dash: a mapped place, a bare street as venue, or nothing."""
    if UNKNOWN in title:
        return (None, None)
    head, sep, suffix = title.rpartition('—')
    suffix = suffix.strip()
    if not sep or not suffix:
        return (None, None)
    return PLACE_FIX.get(suffix, (suffix, None))


def _text(item, tag):
    value = item.findtext(tag)
    return value.strip() if value else None


def _draft(item) -> dict:
    title = _text(item, 'title') or ''
    desc = _text(item, 'description') or ''
    published = _published(item)
    title_place = place_from_title(title)
    if any(title_place):                        # the suffix is consumed, so it leaves the title
        title = title.rpartition('—')[0].strip()
    place = _place_from_description(desc) or title_place
    return {
        'source': NAME,
        'class': CLASS,
        'source_id': _text(item, 'guid'),
        'title': title,
        'venue': place[0],
        'city': place[1],
        'street': None,
        'start': parse_hebrew_when(desc, published) if published else None,
        'end': None,
        'price_from': None,
        'price_max': None,
        'soldout': None,
        'desc': desc,
        'url': _text(item, 'link'),
        'tags': [],
    }


def _published(item) -> datetime | None:
    raw = _text(item, 'pubDate')
    if not raw:
        return None
    try:
        moment = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    return moment.astimezone(_tz()) if moment.tzinfo else None


def parse(payload: str) -> list[dict]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        log.warning('popit: unreadable RSS: %s', exc)
        return []
    items = root.findall('./channel/item')
    if not items:
        log.warning('popit: no <item> under <channel>')
        return []
    drafts = []
    for index, item in enumerate(items):
        draft = _draft(item)
        if not draft['title']:
            log.warning('popit[%d]: dropped, no title', index)
            continue
        # 2309 has a date but no clock: start stays None and normalize.record is the one that drops it.
        if draft['start'] is None:
            log.warning('popit[%d]: no start in the prose', index)
        drafts.append(draft)
    return drafts
