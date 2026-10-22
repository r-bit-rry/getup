"""Draft -> record: title form, bucket day, and the one trust boundary before anything is written."""

import logging
import math
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import geo, venues

log = logging.getLogger('getup')

try:
    TZ = ZoneInfo('Asia/Jerusalem')
except Exception as exc:                     # a silent UTC fallback would misfile every night
    raise RuntimeError('getup: no tz data for Asia/Jerusalem') from exc

SERVE_DAYS = 30
MIN_START = 946684800                        # 2000-01-01T00:00:00Z
MAX_START = 4102444800                       # 2100-01-01T00:00:00Z
MAX_SPAN = 12 * 3600
NIGHT_END = 6                                # a start before 06:00 belongs to the night before
DESC_LIMIT = 600

EMOJI = re.compile('[\U0001f000-\U0001faff\u2600-\u27bf\u2190-\u21ff\ufe0f\u200d]')
PUNCT = re.compile(r'[^\w\s]')
APOSTROPHE = re.compile('[\'"]')


def norm_title(text) -> str:
    """The one title form: dedup, touring and classify all read this.

    A geresh/gershayim is part of the word, so it is deleted rather than turned into a space:
    ``ג׳אז`` and ``גאז`` are one title. Any other punctuation separates words.
    """
    value = venues.NIQQUD.sub('', str(text or '')).translate(venues.QUOTES)
    return ' '.join(PUNCT.sub(' ', EMOJI.sub('', APOSTROPHE.sub('', value))).split()).lower()


def bucket_day(start: int) -> str:
    moment = datetime.fromtimestamp(start, TZ)
    day = moment.date()
    if moment.hour < NIGHT_END:
        day -= timedelta(days=1)
    return day.isoformat()


def horizon(today: str) -> list[str]:
    """The 30 dates today … today + 29, the only days a run may store."""
    first = date.fromisoformat(today)
    return [(first + timedelta(days=n)).isoformat() for n in range(SERVE_DAYS)]


def id_for(venue_id: str, day: str, start: int) -> str:
    return f'{venue_id}|{day}|{datetime.fromtimestamp(start, TZ):%H:%M}'


def desc_cap(text, limit: int = DESC_LIMIT) -> str:
    value = ' '.join(str(text or '').split())
    if len(value) <= limit:
        return value
    cut = value[:limit]
    if ' ' in cut:
        cut = cut.rsplit(' ', 1)[0]
    return cut.rstrip() + '…'


def _int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) else None
    if isinstance(value, str):
        try:
            return int(value.strip().replace(',', ''))
        except ValueError:
            return None
    return None


def _drop(draft, why: str):
    log.warning('getup: dropped %s %s: %s', draft.get('source'), draft.get('source_id'), why)
    return None


def record(draft) -> dict | None:
    """The client-shaped record, or None with exactly one warning naming source and source_id."""
    draft = draft if isinstance(draft, dict) else {}
    title = ' '.join(str(draft.get('title') or '').split())
    start = draft.get('start')
    venue_id = draft.get('venue_id')
    venue_id = venue_id.strip() if isinstance(venue_id, str) else ''
    if not title:
        return _drop(draft, 'no title')
    if not isinstance(start, int) or isinstance(start, bool) or not MIN_START <= start <= MAX_START:
        return _drop(draft, f'unusable start {start!r}')
    if not venue_id:
        return _drop(draft, 'no venue')
    end = _int(draft.get('end'))
    if end is None or not start < end <= start + MAX_SPAN:
        end = None
    price_from = _int(draft.get('price_from'))
    price_max = _int(draft.get('price_max'))
    url = draft.get('url')
    source_class = draft.get('class')
    day = bucket_day(start)
    return {
        'id': id_for(venue_id, day, start),
        'day': day,
        'start': start,
        'end': end,
        'title': title,
        'venue_id': venue_id,
        'city': draft.get('city'),
        'price_from': price_from,
        'price_max': price_max,
        'soldout': bool(draft.get('soldout')),
        'free': price_from == 0,
        'free_until': None,
        'desc': desc_cap(draft.get('desc')),
        'source': {'class': source_class, 'name': draft.get('source')},
        'urls': {'tickets': url if source_class == 'ticketing' else None,
                 'community': None, 'source': url},
        'notes': [],
        'enrichment': [],
        'seen': {},
        'tags': [tag for tag in draft.get('tags') or [] if isinstance(tag, str)],
        'lat': draft.get('lat'),
        'lon': draft.get('lon'),
        'drive_min': draft.get('drive_min'),
        'drive_approx': draft.get('coords_source') == geo.SHORTCUT,
    }
