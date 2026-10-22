"""Issue bodies -> canonical drafts: the one trust boundary between a GitHub form and the site.

Task 2 owns parsing and validation. The poll, the guard and the receipts live here too (Task 4).
"""

import re
from datetime import date, datetime

from . import normalize

EVENT_FIELDS = ('שם האירוע', 'שם המקום', 'עיר', 'תאריך', 'שעה', 'מחיר',
                'קישור לאירוע', 'קישור לכרטיסים', 'קהילה סגורה (קישור לקבוצה)', 'תיאור')
EVENT_REQUIRED = EVENT_FIELDS[:5]
# The form `id:` values in the same order as the field tuples; the drift test compares these.
EVENT_IDS = ('event-title', 'event-venue', 'event-city', 'event-date', 'event-time',
             'event-price', 'event-url', 'event-tickets', 'event-gated', 'event-desc')
SOURCE_FIELDS = ('שם המקור', 'כתובת המקור', 'סוג המקור', 'מה חסר היום')
SOURCE_IDS = ('source-name', 'source-url', 'source-kind', 'source-gap')
PREFS_FIELDS = ('סוג הכלל', 'שם המקום', 'עיר', 'אמן או שם מופע', 'למה')
PREFS_IDS = ('prefs-kind', 'prefs-venue', 'prefs-city', 'prefs-artist', 'prefs-reason')

SOURCE_KINDS = {'לוח מכירות': 'ticketing', 'אגרגטור': 'aggregator', 'לילה': 'nightlife',
                'אתר של מקום': 'venue', 'רשת חברתית': 'social'}

TITLE_LIMIT = 200

SECTION = re.compile(r'^### (.+)$', re.M)
BOX = re.compile(r'^[ \t]*-[ \t]*\[([ xX])\][ \t]*(.+?)[ \t]*$', re.M)
LINK = re.compile(r'^https?://\S+$')
CLOCK = re.compile(r'^\d{1,2}:\d{2}$')
PRICE = re.compile(r'^[₪\s]*(\d[\d,]*)[₪\s]*$')
NO_RESPONSE = '_No response_'
UNKNOWN_FORM = 'טופס לא מזוהה'
BAD = object()


def _text(value) -> str:
    return ' '.join(str(value or '').split())


def _link(value) -> bool:
    return bool(LINK.match(value or ''))


def _price(value):
    """None for unknown, 0 for free, an int of shekels, or BAD — never a guess."""
    text = _text(value)
    if not text:
        return None
    if text == 'חינם':
        return 0
    found = PRICE.match(text)
    return int(found.group(1).replace(',', '')) if found else BAD


def parse_form(body: str) -> dict:
    """`### label` sections become keys; a checked box adds `label: 'x'`, an unchecked one nothing."""
    text = str(body or '')
    marks = list(SECTION.finditer(text))
    fields = {}
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        label = mark.group(1).strip()
        value = text[mark.end():end].strip()
        boxes = BOX.findall(value)
        if boxes:
            value = BOX.sub('', value).strip()
            for tick, name in boxes:
                if tick.lower() == 'x':
                    fields[_text(name)] = 'x'
            if not value:
                continue
        fields[label] = '' if value == NO_RESPONSE else value
    return fields


def event_draft(fields: dict, today: str) -> tuple:
    """The canonical human draft, or None plus every problem named in form order."""
    problems = []
    title = _text(fields.get('שם האירוע'))
    if not title:
        problems.append('שם האירוע')
    elif len(title) > TITLE_LIMIT:
        problems.append(f'שם האירוע (עד {TITLE_LIMIT} תווים)')
    venue = _text(fields.get('שם המקום'))
    if not venue:
        problems.append('שם המקום')
    city = _text(fields.get('עיר'))
    if not city:
        problems.append('עיר')

    day = _text(fields.get('תאריך'))
    clock = _text(fields.get('שעה'))
    day_ok = False
    start = None
    if not day:
        problems.append('תאריך')
    else:
        try:
            date.fromisoformat(day)
            day_ok = True
        except ValueError:
            problems.append('תאריך (YYYY-MM-DD)')
    clock_ok = False
    if not clock:
        problems.append('שעה')
    elif not CLOCK.match(clock):
        problems.append('שעה (HH:MM)')
    else:
        clock_ok = True
    if day_ok and clock_ok:
        try:
            moment = datetime.fromisoformat(f'{day}T{clock}')
        except ValueError:                  # 24:00 passes the shape and is still not a time
            problems.append('שעה (HH:MM)')
        else:
            start = int(moment.replace(tzinfo=normalize.tz()).timestamp())
            if normalize.bucket_day(start) < today:
                problems.append('תאריך שכבר עבר')

    price = _price(fields.get('מחיר'))
    if price is BAD:
        problems.append('מחיר (מספר בשקלים או חינם)')

    url = _text(fields.get('קישור לאירוע'))
    if url and not _link(url):
        problems.append('קישור לאירוע (https://)')
    tickets = _text(fields.get('קישור לכרטיסים'))
    if tickets and not _link(tickets):
        problems.append('קישור לכרטיסים (https://)')

    if problems:
        return None, problems
    gated = fields.get('קהילה סגורה (קישור לקבוצה)') == 'x'
    return {
        'class': 'human', 'source': 'github', 'title': title, 'venue': venue, 'city': city,
        'start': start,
        'url': url or None,
        'tickets': tickets or None,          # only the tickets field, never the event page
        'community': url if gated else None,
        'price_from': price,
        'desc': normalize.desc_cap(fields.get('תיאור')),
    }, []


def source_record(fields: dict) -> tuple:
    problems = []
    name = _text(fields.get('שם המקור'))
    if not name:
        problems.append('שם המקור')
    url = _text(fields.get('כתובת המקור'))
    if not _link(url):
        problems.append('כתובת המקור (https://)')
    kind = SOURCE_KINDS.get(_text(fields.get('סוג המקור')))
    if not kind:
        problems.append('סוג המקור')
    if problems:
        return None, problems
    return {'name': name, 'url': url, 'kind': kind,
            'note': _text(fields.get('מה חסר היום'))}, []
