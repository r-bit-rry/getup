"""Venue identity: city spelling collapse, the alias index and provisional entries."""

import hashlib
import os
import re

from . import write

# The cities the committed capture can place. Kept here as the vocabulary that decides whether a
# trailing ", <locality>" is a city (and may leave a name) or part of the hall's name.
CITY_CAPTURE = 'docs/research/2026-10-21/geo-drive.json'

CITY_FIX = {
    'מודיעין': 'מודיעין מכבים רעות',
    'תל אביב-יפו': 'תל אביב',
    'איירפורט סיטי': 'נתב"ג',
    'קרית שדה התעופה': 'נתב"ג',
    'פתח תקוה': 'פתח תקווה',
}

NIQQUD = re.compile('[\u0591-\u05bd\u05bf\u05c1\u05c2\u05c4\u05c5\u05c7]')
QUOTES = str.maketrans({'״': '"', '”': '"', '“': '"', '„': '"',
                        '׳': "'", '’': "'", '‘': "'"})

_known = None


def known_cities() -> frozenset:
    global _known
    if _known is None:
        data = write.read_json(CITY_CAPTURE, {}) or {}
        geo = data.get('geo') if isinstance(data, dict) else None
        _known = frozenset(map(norm_city, geo if isinstance(geo, dict) else ())) \
            | frozenset(CITY_FIX.values())
    return _known


def norm_city(city) -> str:
    """The city spelling the registry uses; '' when the value is no city at all."""
    text = NIQQUD.sub('', ' '.join(str(city or '').split())).translate(QUOTES)
    if not text or any(ch.isdigit() for ch in text):    # a street leaked into the city slot
        return ''
    text = CITY_FIX.get(text, text)
    if text.startswith('קרית '):
        text = 'קריית ' + text[len('קרית '):]
    return CITY_FIX.get(text, text)


def norm_name(name) -> str:
    text = NIQQUD.sub('', ' '.join(str(name or '').split())).translate(QUOTES)
    text = re.sub(r'[\u05be\-\u2010-\u2015]', ' ', text)
    return ' '.join(text.split()).lower()


def norm_name_loose(name) -> str:
    text = re.sub(r'\([^)]*\)', ' ', norm_name(name))
    return ' '.join(re.sub(r'[^\w\s]', '', text).split())


def strip_city_suffix(venue, city) -> str:
    """Drop a trailing ", <city>" only when the tail is a city this registry can place."""
    text = ' '.join(str(venue or '').split())
    head, sep, tail = text.rpartition(', ')
    if not sep:
        return text
    tail = norm_city(tail)
    if tail and (tail == norm_city(city) or tail in known_cities()):
        return head
    return text


def provisional_id(name, city) -> str:
    key = f'{norm_name(name)}|{norm_city(city)}'
    return 'v_' + hashlib.sha1(key.encode('utf-8')).hexdigest()[:10]


def _forms(venue):
    return [venue.get('name') or '', *(venue.get('aliases') or [])]


def alias_index(registry: dict) -> dict:
    """(normalised form, normalised city) -> venue id, for every name, alias and cityless base."""
    index = {}
    for venue_id, venue in registry.items():
        city = norm_city(venue.get('city'))
        for form in _forms(venue):
            for text in {form, strip_city_suffix(form, city)}:
                index[(norm_name(text), city)] = venue_id
                index[(norm_name_loose(text), city)] = venue_id
    return index


def _unique_name(registry: dict) -> dict:
    """Name -> id, only where exactly one venue anywhere carries that name."""
    owners, unique = {}, {}
    for venue_id, venue in registry.items():
        keys = set()
        for form in _forms(venue):
            for text in (form, strip_city_suffix(form, venue.get('city'))):
                keys.update((norm_name(text), norm_name_loose(text)))
        for key in sorted(keys):        # one venue counts once however many forms agree
            owners[key] = owners.get(key, 0) + 1
            unique.setdefault(key, venue_id)
    return {key: unique[key] for key in sorted(owners) if owners[key] == 1}


def _provision(registry: dict, name: str, city: str) -> str:
    venue_id = provisional_id(name, city)
    if venue_id not in registry:
        registry[venue_id] = {
            'id': venue_id, 'name': name, 'aliases': [],
            'city': city, 'lat': None, 'lon': None, 'drive_min': None,
            'coords_source': 'unresolved', 'tier': 'room', 'parking': None,
            'access': None, 'transport': None,
            'social': {'instagram': None, 'facebook': None},
        }
    return venue_id


def resolve(registry: dict, venue, city) -> str | None:
    """The venue id for a source string, provisioning one when the registry does not know it."""
    name = ' '.join(str(venue or '').split())
    if not name:
        return None
    place = norm_city(city)
    candidates = [name, strip_city_suffix(name, place)]
    index = alias_index(registry)
    for text in candidates:
        for key in (norm_name(text), norm_name_loose(text)):
            found = index.get((key, place))
            if found:
                return found
    if not place:
        # No city was given: borrow the one hall with this name, unless several cities have it.
        unique = _unique_name(registry)
        for text in candidates:
            for key in (norm_name(text), norm_name_loose(text)):
                found = unique.get(key)
                if found:
                    return found
    return _provision(registry, name, place)


def city_of(registry: dict, venue_id: str, fallback=None):
    """The registry owns the city; a source's city is the last resort."""
    return (registry.get(venue_id) or {}).get('city') or fallback


def load(root: str) -> dict:
    data = write.read_json(os.path.join(root, 'venue', 'venues.json'), {})
    return data if isinstance(data, dict) else {}


def save(root: str, registry: dict) -> bool:
    return write.write_json(os.path.join(root, 'venue', 'venues.json'), registry)
