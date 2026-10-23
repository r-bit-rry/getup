"""Derived signals: the p90 price line, commitment, notability, free-until and venue facts."""

import math
import re

from .normalize import norm_title
from .venues import norm_city

FIXED_SEAT = frozenset({'festival', 'theatre', 'orchestra'})
PLAN_DRIVE = 60
ABSOLUTE_EXPENSIVE = 200
NOTE_LIMIT = 5

FREE_HE = re.compile(r'(?:חינם|חופשי)\s+עד\s+(\d{1,2})[:.](\d{2})')
FREE_EN = re.compile(r'free\s+before\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)', re.I)

NOTE_FIELDS = (('parking', 'חניה'), ('access', 'נגישות'), ('transport', 'תחבורה'))


def p90(prices: list[float]):
    """Nearest rank: the smallest price at or above 90% of the set."""
    values = sorted(prices)
    if not values:
        return None
    return values[min(len(values) - 1, math.floor(0.9 * len(values)))]


def touring(records: list[dict]) -> dict[str, int]:
    """Titles and their distinct cities, over the whole source payload, not the served horizon."""
    cities = {}
    for rec in records if isinstance(records, list) else []:
        if not isinstance(rec, dict):
            continue
        city = norm_city(rec.get('city'))
        if city:
            cities.setdefault(norm_title(rec.get('title')), set()).add(city)
    return {title: len(seen) for title, seen in cities.items()}


def commitment(rec: dict) -> str:
    """A fixed seat or a real drive is planning; an unknown drive is never a reason to plan."""
    drive = (rec or {}).get('drive_min')
    planned = (rec or {}).get('format') in FIXED_SEAT \
        or (isinstance(drive, int) and not isinstance(drive, bool) and drive >= PLAN_DRIVE)
    return 'plan_ahead' if planned else 'jump_in'


def notable(rec: dict, cities: int, registry: dict) -> bool:
    """Only a ticket seller's event can be notable: the other sources cannot vouch for it."""
    rec = rec or {}
    if (rec.get('source') or {}).get('class') != 'ticketing':
        return False
    venue = registry.get(rec.get('venue_id')) or {}
    price = rec.get('price_from')
    return (cities >= 2 or venue.get('tier') == 'major'
            or (isinstance(price, int) and price >= ABSOLUTE_EXPENSIVE))


def _clock(hour: int, minute: int):
    return f'{hour:02d}:{minute:02d}' if 0 <= hour <= 23 and 0 <= minute <= 59 else None


def free_until(text):
    """The free-entry cutoff stated in prose, in either language; None when unstated."""
    text = str(text or '')
    found = FREE_HE.search(text)
    if found:
        return _clock(int(found.group(1)), int(found.group(2)))
    found = FREE_EN.search(text)
    if found:
        hour, minute = int(found.group(1)) % 12, int(found.group(2) or 0)
        if found.group(3).lower() == 'pm':
            hour += 12
        return _clock(hour, minute)
    return None


def venue_notes(rec: dict, venue: dict | None) -> list[str]:
    """The event's own notes plus the registry's facts, each prefix at most once."""
    notes = list((rec or {}).get('notes') or [])
    if venue:
        for field, label in NOTE_FIELDS:
            value = ' '.join(str(venue.get(field) or '').split())
            if not value or any(note.startswith(f'{label}:') for note in notes):
                continue
            notes.append(f'{label}: {value}')
    return notes[:NOTE_LIMIT]


def signals(records: list[dict], *, touring: dict[str, int], registry: dict) -> list[dict]:
    """One pass over the retained set: its own p90 is the only threshold there is."""
    records = records if isinstance(records, list) else []
    threshold = p90([r.get('price_from') for r in records
                     if isinstance(r.get('price_from'), int)
                     and not isinstance(r.get('price_from'), bool)])
    out = []
    for rec in records:
        price = rec.get('price_from')
        cities = touring.get(norm_title(rec.get('title')), 0)
        venue = registry.get(rec.get('venue_id'))
        out.append({**rec,
                    'expensive': isinstance(price, int) and not isinstance(price, bool)
                    and (price >= ABSOLUTE_EXPENSIVE
                         or (threshold is not None and price >= threshold)),
                    'commitment': commitment(rec),
                    'free_until': free_until(rec.get('desc')) or rec.get('free_until'),
                    'notable': notable(rec, cities, registry),
                    'notes': venue_notes(rec, venue)})
    return out
