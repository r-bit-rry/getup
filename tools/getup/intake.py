"""Issue bodies -> canonical drafts: the one trust boundary between a GitHub form and the site.

`github.py` owns HTTP; this module owns the rules: what a form means, who may submit one, what
gets stored, and what the issue is told.
"""

import html
import json
import os
import re
from datetime import date, datetime

from . import dedup, human, normalize, venues, write
from .github import GithubError, client_from_env

ASSOCIATIONS = frozenset({'OWNER', 'MEMBER'})
KINDS = ('event', 'source')
RECEIPT_MARK = '<!-- getup:record -->'
INFO_MARK = '<!-- getup:needs-info -->'
FAULT_MARK = '<!-- getup:fault -->'     # never a needs-info: a fault must not silence a real one
MERGED_LEAD = 'מוזג לאירוע קיים. הרשומה הקנונית:'
INGESTED_LEAD = 'נקלט. הרשומה הקנונית:'
SOURCE_LEAD = 'נקלט. בקשת המקור:'
PREFS_LEAD = 'נקלט. ההעדפה נוספה ל־prefs.json ותיכנס לתוקף ברענון הבא.'
STATE_FAULT = 'לא נקלט. קובץ מצב פגום: '
SAVE_FAULT = 'לא נקלט. כתיבת קובץ המצב נכשלה: '

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
PREFS_KINDS = {'לא להציג': 'never', 'תמיד להציג': 'always'}

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
        clock = clock.zfill(5)              # 9:30 is 09:30; fromisoformat refuses the short hour
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


def prefs_rule(fields: dict, registry: dict) -> tuple:
    """`{'kind', 'rule'}` for one preference form, or None plus every problem named.

    A venue is resolved through `venues.find`, which never provisions: reading a preference must
    not curate the registry. Both fields filled is one rule and therefore an AND.
    """
    problems = []
    kind = PREFS_KINDS.get(_text(fields.get('סוג הכלל')))
    if not kind:
        problems.append('סוג הכלל')
    rule = {}
    venue = _text(fields.get('שם המקום'))
    if venue:
        venue_id = venues.find(registry, venue, fields.get('עיר'))
        if venue_id is None:
            problems.append('שם המקום (לא נמצא במאגר)')
        else:
            rule['venue_id'] = venue_id
    artist = _text(fields.get('אמן או שם מופע'))
    if artist:
        rule['artist'] = artist
    if not venue and not artist:
        problems.append('שם המקום או אמן')
    if problems:
        return None, problems
    return {'kind': kind, 'rule': rule}, []


def prefs_file(root: str) -> str:
    return os.path.join(root, 'prefs.json')


def add_rule(root: str, kind: str, rule: dict) -> bool:
    """Append a rule to prefs.json; True only when the file changed.

    The browser applies the file; the pipeline only ever appends. A corrupt file raises instead
    of being replaced, because rebuilding it would erase the owner's rules.
    """
    if kind not in ('never', 'always'):
        raise ValueError(f'unknown prefs kind: {kind!r}')
    if not isinstance(rule, dict) or not rule:
        raise ValueError('prefs rule is empty')
    path = prefs_file(root)
    data = write.read_json_strict(path) if os.path.exists(path) else {}
    if not isinstance(data, dict):
        raise ValueError(f'{path}: prefs is not an object')
    for name in ('never', 'always'):
        data.setdefault(name, [])
        if not isinstance(data[name], list):
            raise ValueError(f'{path}: {name} is not a list')
    if rule in data[kind]:
        return False
    data[kind].append(rule)
    write.write_json(path, data)
    return True


def detect(fields: dict):
    """Which form a body is, from the headings it carries; None is a body nobody wrote a form for."""
    if 'שם האירוע' in fields:
        return 'event'
    if 'שם המקור' in fields:
        return 'source'
    if 'סוג הכלל' in fields:
        return 'prefs'
    return None


def eligible(issue: dict) -> bool:
    """The only defence (ADR-0008): a stranger's issue is never processed, never answered."""
    return (issue or {}).get('author_association') in ASSOCIATIONS


def info(problems: list) -> str:
    return INFO_MARK + '\nלא נקלט. נדרש: ' + ' · '.join(problems)


def receipt(payload: dict, lead: str) -> str:
    """The record, escaped inside <pre>: a title with markup or backticks cannot break the comment.

    Quotes are not escaped: inside a text node they are literal, and the JSON stays copyable.
    """
    body = json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True)
    return f'{RECEIPT_MARK}\n{lead}\n<pre>{html.escape(body, quote=False)}</pre>'


def _said(client, number: int, marker: str) -> bool:
    """A marker only counts from an owner, a member or a bot account (ours): the text is copyable,
    the association and the account type are not. A stranger's `<!-- getup:record -->` is noise."""
    def trusted(row) -> bool:
        row = row or {}
        return (row.get('author_association') in ASSOCIATIONS
                or (row.get('user') or {}).get('type') == 'Bot')

    return any(marker in str((row or {}).get('body') or '')
               for row in client.comments(number) if trusted(row))


def _labelled(issue: dict, name: str) -> bool:
    rows = issue.get('labels') or []
    return any((row.get('name') if isinstance(row, dict) else row) == name for row in rows)


def _venue_key(registry: dict, draft: dict):
    return venues.resolve(registry, draft.get('venue'), draft.get('city'))


def same_event(store: dict, number: int, draft: dict, registry: dict) -> bool:
    """Another issue already holds this event: same resolved venue, start within dedup.WINDOW.

    The issue's own entry never counts, so a correction is an update and not a merge.
    """
    scratch = dict(registry)            # resolve provisions in memory; this module must not curate
    mine = _venue_key(scratch, draft)
    start = draft.get('start')
    if mine is None or not isinstance(start, int) or isinstance(start, bool):
        return False
    for key, other in store.items():
        if str(key) == str(number) or not isinstance(other, dict):
            continue
        other_start = other.get('start')
        if not isinstance(other_start, int) or isinstance(other_start, bool):
            continue
        if abs(other_start - start) > dedup.WINDOW:
            continue
        if _venue_key(scratch, other) == mine:
            return True
    return False


def _needs_info(client, number: int, problems: list) -> dict:
    if not _said(client, number, INFO_MARK):
        client.comment(number, info(problems))
    client.add_label(number, 'needs-info')
    return {'number': number, 'result': 'needs-info', 'problems': problems}


def _fault(client, number: int, lead: str, exc: Exception) -> dict:
    """One issue fails and says why on the issue; the comment is best effort, the result is the record."""
    try:
        client.comment(number, f'{FAULT_MARK}\n{lead}{exc}')
    except GithubError:
        pass
    return {'number': number, 'result': 'failed', 'problems': [str(exc)]}


def _event(root: str, number: int, issue: dict, fields: dict, client, today: str) -> dict:
    draft, problems = event_draft(fields, today)
    if problems:
        return _needs_info(client, number, problems)
    try:                                # a corrupt file raises here and only here
        store = human.load(root)
        registry = venues.load(root)
    except ValueError as exc:           # the file is named on the issue; the poll moves on
        return _fault(client, number, STATE_FAULT, exc)
    # A correction is an update, not a merge: only an issue without its own draft can merge.
    merged = str(number) not in store and same_event(store, number, draft, registry)
    changed = human.put(store, number, draft)
    try:
        human.save(root, store)         # the draft, never a placed record: build.place owns that
    except OSError as exc:              # a full disk is this issue's failure, not the poll's
        return _fault(client, number, SAVE_FAULT, exc)
    if changed or not _said(client, number, RECEIPT_MARK):
        client.comment(number, receipt(draft, MERGED_LEAD if merged else INGESTED_LEAD))
    client.add_label(number, 'processed')
    if _labelled(issue, 'needs-info'):
        client.remove_label(number, 'needs-info')
    return {'number': number, 'result': 'merged' if merged else 'ingested', 'problems': []}


def _source(number: int, fields: dict, client) -> dict:
    record, problems = source_record(fields)
    if problems:
        return _needs_info(client, number, problems)
    if not _said(client, number, RECEIPT_MARK):
        client.comment(number, receipt(record, SOURCE_LEAD))
    client.add_label(number, 'processed')
    return {'number': number, 'result': 'source', 'problems': []}


def _prefs(root: str, number: int, fields: dict, client) -> dict:
    spec, problems = prefs_rule(fields, venues.load(root))   # a corrupt registry raises, and is named
    if problems:
        return _needs_info(client, number, problems)
    changed = add_rule(root, spec['kind'], spec['rule'])
    if changed or not _said(client, number, RECEIPT_MARK):
        client.comment(number, receipt(spec, PREFS_LEAD))
    client.add_label(number, 'processed')
    return {'number': number, 'result': 'prefs', 'problems': []}


def ingest(root: str, issue: dict, *, client, today: str) -> dict:
    """One issue, one result; never raises for a bad issue, a bad form or a corrupt state file."""
    number = (issue or {}).get('number')
    if not eligible(issue):
        return {'number': number, 'result': 'skipped', 'problems': []}
    try:
        fields = parse_form((issue or {}).get('body'))
        kind = detect(fields)
        if kind is None:
            return _needs_info(client, number, [UNKNOWN_FORM])
        if kind == 'source':
            return _source(number, fields, client)
        if kind == 'prefs':
            return _prefs(root, number, fields, client)
        return _event(root, number, issue, fields, client, today)
    except GithubError as exc:
        return {'number': number, 'result': 'failed', 'problems': [str(exc)]}
    except ValueError as exc:           # a corrupt state file: the file is named on the issue
        return _fault(client, number, STATE_FAULT, exc)


def poll(root: str, *, client, today: str) -> list:
    """Verify the labels once, then one issue at a time, lowest number first."""
    client.ensure_labels()
    rows = sorted(client.issues(), key=lambda row: (row or {}).get('number') or 0)
    return [ingest(root, row, client=client, today=today) for row in rows]


def check_state(root: str) -> None:
    """Strictly read every state file before a run can read it half-way or overwrite it.

    A corrupt store is a startup fault, not one issue's problem: the command exits 5 before polling.
    """
    human.load(root)
    venues.load(root)
    path = prefs_file(root)
    if os.path.exists(path):
        data = write.read_json_strict(path)     # names the file and the fault
        if not isinstance(data, dict):
            raise ValueError(f'{path}: prefs is not an object')
