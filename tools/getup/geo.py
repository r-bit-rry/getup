"""Geocoding, drive minutes and the committed city-centroid shortcut."""

import json
import logging
import time
import urllib.parse

from . import venues, write

log = logging.getLogger('getup')

SHORTCUT = 'shortcut: city centroid, upgrade when venue geocodes exist'
CITY_CAPTURE = venues.CITY_CAPTURE
ORIGIN = (32.3286, 34.8566)                 # Netanya
NOMINATIM = 'https://nominatim.openstreetmap.org/search'
OSRM = 'https://router.project-osrm.org/route/v1/driving'


class RateLimiter:
    def __init__(self, min_interval: float = 1.0, *, clock=time.monotonic, sleep=time.sleep):
        self.min_interval, self._clock, self._sleep, self._last = min_interval, clock, sleep, None

    def wait(self) -> None:
        now = self._clock()
        if self._last is not None:
            delay = self.min_interval - (now - self._last)
            if delay > 0:
                self._sleep(delay)
        self._last = self._clock()


def geocode(venue: str, city: str, *, fetch, limiter=None) -> tuple | None:
    query = urllib.parse.urlencode({'q': f'{venue}, {city}', 'format': 'json',
                                    'limit': '1', 'countrycodes': 'il'})
    if limiter is not None:
        limiter.wait()
    try:
        hits = json.loads(fetch(f'{NOMINATIM}?{query}'))
        return float(hits[0]['lat']), float(hits[0]['lon'])
    except Exception:
        return None


def drive_minutes(dest: tuple, origin: tuple = ORIGIN, *, fetch) -> int | None:
    points = ';'.join(f'{lon},{lat}' for lat, lon in (origin, dest))
    try:
        route = json.loads(fetch(f'{OSRM}/{points}?overview=false'))
        return int(round(float(route['routes'][0]['duration']) / 60))
    except Exception:
        return None


def fill(registry: dict, *, fetch, limiter=None, warn=None) -> tuple:
    """Geocode the entries that have no point; cache minutes; never invent either."""
    limiter = limiter if limiter is not None else RateLimiter()
    geocoded = failed = 0
    for venue_id in sorted(registry):
        venue = registry[venue_id]
        if venue.get('lat') is None or venue.get('lon') is None:
            name, city = venue.get('name') or '', venue.get('city') or ''
            if not city:                     # "venue, None" is not a query; the entry stays unresolved
                continue
            point = geocode(name, city, fetch=fetch, limiter=limiter)
            if point is None:
                failed += 1
                venue.update(lat=None, lon=None, drive_min=None, coords_source='unresolved')
                message = f'getup: no geocode for {name} in {city}'
                (warn or log.warning)(message)
                continue
            venue['lat'], venue['lon'] = point
            venue['coords_source'] = 'nominatim'
            geocoded += 1
        if venue.get('drive_min') is None and venue.get('lat') is not None:
            minutes = drive_minutes((venue['lat'], venue['lon']), fetch=fetch)
            if minutes is not None:
                venue['drive_min'] = minutes
    return registry, geocoded, failed


def seed(registry: dict, path: str = CITY_CAPTURE) -> int:
    """Pin every entry whose city the capture places, without touching a real geocode."""
    capture = write.read_json(path, {}) or {}
    points, minutes = {}, {}
    for city, point in (capture.get('geo') or {}).items():
        points.setdefault(venues.norm_city(city), point)
    for city, legs in (capture.get('drive') or {}).items():
        minutes.setdefault(venues.norm_city(city), legs.get('min') if isinstance(legs, dict) else None)
    pinned = 0
    for venue_id in sorted(registry):
        venue, city = registry[venue_id], venues.norm_city(registry[venue_id].get('city'))
        filled = False
        if (venue.get('lat') is None or venue.get('lon') is None) and city in points:
            venue['lat'], venue['lon'] = points[city]
            venue['coords_source'] = SHORTCUT
            filled = True
        if venue.get('drive_min') is None and minutes.get(city) is not None:
            venue['drive_min'] = minutes[city]
            filled = True
        pinned += filled
    return pinned
