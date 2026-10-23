"""Venue identity: city spelling collapse, the alias index and provisional entries."""

import hashlib
import os
import re
from collections import Counter

from . import write

# The cities the committed capture can place. Kept here as the vocabulary that decides whether a
# trailing ", <locality>" is a city (and may leave a name) or part of the hall's name.
# Anchored to the module, not the cwd: a capture run from /tmp must read the same file.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CITY_CAPTURE = os.path.join(ROOT, 'docs', 'research', '2026-10-21', 'geo-drive.json')

CITY_FIX = {
    'מודיעין': 'מודיעין מכבים רעות',
    'תל אביב-יפו': 'תל אביב',
    'איירפורט סיטי': 'נתב"ג',
    'קרית שדה התעופה': 'נתב"ג',
    'פתח תקוה': 'פתח תקווה',
}

# A city a venue name states that the capture has no centroid for: the name still places it,
# the centroid shortcut cannot, and geo.fill geocodes it like any other venue.
NAME_ONLY_CITIES = ('רמת השרון',)

NIQQUD = re.compile('[\u0591-\u05bd\u05bf\u05c1\u05c2\u05c4\u05c5\u05c7]')
QUOTES = str.maketrans({'״': '"', '”': '"', '“': '"', '„': '"',
                        '׳': "'", '’': "'", '‘': "'"})
HALL_WORD = re.compile(r'(?<!\S)אולם(?!\S)')

_known = None


def known_cities() -> frozenset:
    global _known
    if _known is None:
        data = write.read_json(CITY_CAPTURE, {}) or {}
        geo = data.get('geo') if isinstance(data, dict) else None
        _known = frozenset(map(norm_city, geo if isinstance(geo, dict) else ())) \
            | frozenset(CITY_FIX.values()) | frozenset(NAME_ONLY_CITIES)
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
    text = re.sub(r'קרית\b', 'קריית', text)      # the spelling of a place inside the hall's name
    return ' '.join(text.split()).lower()


def norm_name_loose(name) -> str:
    """Punctuation, the geresh and the bare word 'hall' go; the room itself stays.

    So ``היכל התרבות (אולם 1)`` and ``(אולם 2)`` stay two halls, while ``(אולם מאירהוף)``
    still matches a registry alias written ``(מאירהוף)``.
    """
    text = re.sub(r'[^\w\s]', '', norm_name(name))
    return ' '.join(HALL_WORD.sub(' ', text).split())


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


def city_in_name(venue) -> str:
    """A known city spelled as the last words of the venue name: ``זאפה תל אביב`` is Tel Aviv.

    Longest suffix wins, so ``תל אביב`` is not read as a city that happens to be its last word.
    The name keeps the city: only the city slot gains it.
    """
    forms = {}
    for city in known_cities():
        key = tuple(norm_name(city).split())
        if key:
            forms.setdefault(key, city)
    if not forms:
        return ''
    tokens = norm_name(venue).split()
    for size in range(min(len(tokens), max(map(len, forms))), 0, -1):
        if tuple(tokens[-size:]) in forms:
            return forms[tuple(tokens[-size:])]
    return ''


def provisional_id(name, city) -> str:
    key = f'{norm_name(name)}|{norm_city(city)}'
    return 'v_' + hashlib.sha1(key.encode('utf-8')).hexdigest()[:10]


def _forms(venue):
    return [venue.get('name') or '', *(venue.get('aliases') or [])]


def alias_index(registry: dict) -> dict:
    """(normalised form, normalised city) -> venue id, only where one venue in that city owns it.

    A key two halls share is not identity: resolving it would merge them, so it is absent here
    and `resolve` falls through to a provisional entry instead.
    """
    owners, first = Counter(), {}
    for venue_id, venue in registry.items():
        city = norm_city(venue.get('city'))
        keys = set()
        for form in _forms(venue):
            for text in {form, strip_city_suffix(form, city)}:
                keys.add((norm_name(text), city))
                keys.add((norm_name_loose(text), city))
        for key in keys:            # one venue counts once however many of its forms agree
            owners[key] += 1
            first.setdefault(key, venue_id)
    return {key: first[key] for key in owners if owners[key] == 1}


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


def _read(venue, city):
    """The name, the city and the two lookup forms; None when there is no name at all."""
    name = ' '.join(str(venue or '').split())
    if not name:
        return None
    place = norm_city(city)
    if not place:                   # a known city in the name is a stated city, not decoration
        _, sep, tail = name.rpartition(', ')
        if sep and norm_city(tail) in known_cities():
            place = norm_city(tail)
    if place not in known_cities():     # an absent or unplaceable city may be spelled in the name
        place = city_in_name(name) or place
    return name, place, [name, strip_city_suffix(name, place)]


def find(registry: dict, venue, city) -> str | None:
    """The venue id for a source string, without provisioning: a prefs rule must not curate."""
    read = _read(venue, city)
    if read is None:
        return None
    name, place, candidates = read
    index = alias_index(registry)
    for text in candidates:
        for key in (norm_name(text), norm_name_loose(text)):
            found = index.get((key, place))
            if found:
                return found
    if place not in known_cities():
        # No city, or a spelling the capture cannot place: borrow the one hall with this name.
        unique = _unique_name(registry)
        for text in candidates:
            for key in (norm_name(text), norm_name_loose(text)):
                found = unique.get(key)
                if found:
                    return found
    return None


def resolve(registry: dict, venue, city) -> str | None:
    """The venue id for a source string, provisioning one when the registry does not know it."""
    found = find(registry, venue, city)
    if found:
        return found
    read = _read(venue, city)
    if read is None:
        return None
    name, place, _ = read
    if place and city_in_name(name) == place:
        # A city the name just proved: a cityless entry of that name gains it rather than a twin,
        # so the ids the events already carry keep pointing at the same hall.
        cityless = [venue_id for venue_id, entry in registry.items()
                    if not norm_city(entry.get('city'))
                    and norm_name(entry.get('name')) == norm_name(name)]
        if len(cityless) == 1:
            registry[cityless[0]]['city'] = place
            return cityless[0]
    return _provision(registry, name, place)


def city_of(registry: dict, venue_id: str, fallback=None):
    """The registry owns the city; a source's city is the last resort."""
    return (registry.get(venue_id) or {}).get('city') or fallback


def load(root: str) -> dict:
    """The curated registry. A corrupt file raises: rebuilding it would erase the curation."""
    path = os.path.join(root, 'venue', 'venues.json')
    if not os.path.exists(path):
        return {}
    data = write.read_json_strict(path)
    if not isinstance(data, dict):
        raise ValueError(f'{path}: registry is not an object')
    return data


def save(root: str, registry: dict) -> bool:
    return write.write_json(os.path.join(root, 'venue', 'venues.json'), registry)
