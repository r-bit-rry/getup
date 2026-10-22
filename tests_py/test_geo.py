import unittest
from tools.getup import geo, venues

NOMINATIM = '[{"lat":"32.0771","lon":"34.7753"}]'
OSRM = '{"code":"Ok","routes":[{"duration":1740}]}'


def fake(responses, counter=None):
    def fetch(url, **kw):
        if counter is not None:
            counter.append(url)
        return responses.get('nominatim' if 'nominatim' in url else 'osrm')
    return fetch


def reg(**o):
    return {'v_x': {'id': 'v_x', 'name': 'מועדון', 'aliases': [], 'city': 'חיפה',
                    'lat': None, 'lon': None, 'drive_min': None, 'tier': 'room',
                    'coords_source': 'unresolved', 'parking': None,
                    'access': None, 'transport': None, 'social': {}, **o}}


class GeoTest(unittest.TestCase):
    def test_a_venue_with_coordinates_is_never_geocoded_again(self):
        calls = []
        geo.fill(venues.load('.'), fetch=fake({'nominatim': NOMINATIM, 'osrm': OSRM}, calls))
        self.assertFalse([u for u in calls if 'nominatim' in u])   # every fixture venue has a point

    def test_a_missing_point_is_geocoded_once_and_a_missing_duration_is_cached(self):
        registry, geocoded, failed = geo.fill(reg(), fetch=fake({'nominatim': NOMINATIM, 'osrm': OSRM}))
        self.assertEqual((geocoded, failed), (1, 0))
        self.assertEqual((registry['v_x']['lat'], registry['v_x']['lon']), (32.0771, 34.7753))
        self.assertEqual(registry['v_x']['drive_min'], 29)
        self.assertEqual(registry['v_x']['coords_source'], 'nominatim')

    def test_a_venue_that_does_not_geocode_stays_null_and_carries_no_centroid(self):
        warnings = []
        registry, geocoded, failed = geo.fill(reg(), fetch=fake({'nominatim': '[]'}),
                                              warn=warnings.append)
        self.assertEqual((geocoded, failed), (0, 1))
        self.assertEqual((registry['v_x']['lat'], registry['v_x']['drive_min']), (None, None))
        self.assertEqual(registry['v_x']['coords_source'], 'unresolved')
        self.assertEqual(len(warnings), 1)
        self.assertIn('מועדון', warnings[0])

    def test_a_venue_with_no_city_is_never_queried_as_a_bare_none(self):
        calls = []
        registry, geocoded, failed = geo.fill(reg(city=''), fetch=fake(
            {'nominatim': NOMINATIM, 'osrm': OSRM}, calls))
        self.assertEqual((geocoded, failed), (0, 0))
        self.assertEqual(calls, [])
        self.assertEqual((registry['v_x']['lat'], registry['v_x']['lon'],
                          registry['v_x']['drive_min']), (None, None, None))
        self.assertEqual(registry['v_x']['coords_source'], 'unresolved')

    def test_an_unreachable_router_is_none_not_zero_minutes(self):
        self.assertIsNone(geo.drive_minutes((32.1, 34.8), fetch=lambda url, **k: '{"code":"NoRoute"}'))
        def boom(url, **kw): raise OSError('offline')
        self.assertIsNone(geo.drive_minutes((32.1, 34.8), fetch=boom))
        self.assertIsNone(geo.geocode('x', 'y', fetch=boom))

    def test_nominatim_is_called_at_most_once_per_second(self):
        sleeps, now = [], [0.0]
        lim = geo.RateLimiter(1.0, clock=lambda: now[0], sleep=lambda s: (sleeps.append(s), now.__setitem__(0, now[0] + s)))
        lim.wait(); lim.wait()
        self.assertEqual(len(sleeps), 1)
        self.assertAlmostEqual(sleeps[0], 1.0)

    def test_the_geocode_query_is_venue_comma_city_in_israel(self):
        seen = []
        geo.geocode('אוזן בר', 'תל אביב', fetch=lambda url, **k: seen.append(url) or NOMINATIM)
        self.assertIn('nominatim', seen[0])
        self.assertIn('countrycodes=il', seen[0])
        self.assertIn('%D7%90%D7%95%D7%96%D7%9F', seen[0])          # the venue, url-encoded
        self.assertIn('%D7%AA%D7%9C+%D7%90%D7%91%D7%99%D7%91', seen[0])


class SeedTest(unittest.TestCase):
    def test_the_city_capture_supplies_the_point_and_the_minutes(self):
        registry = reg(city='ראשון לציון')
        self.assertEqual(geo.seed(registry), 1)
        self.assertEqual((registry['v_x']['lat'], registry['v_x']['lon']), (31.9635712, 34.8101149))
        self.assertEqual(registry['v_x']['drive_min'], 42)
        self.assertEqual(registry['v_x']['coords_source'],
                         'shortcut: city centroid, upgrade when venue geocodes exist')

    def test_a_geocoded_point_and_its_minutes_are_never_replaced(self):
        registry = reg(city='חיפה', lat=32.8, lon=34.9, drive_min=61, coords_source='nominatim')
        self.assertEqual(geo.seed(registry), 0)
        self.assertEqual((registry['v_x']['lat'], registry['v_x']['drive_min']), (32.8, 61))
        self.assertEqual(registry['v_x']['coords_source'], 'nominatim')

    def test_a_city_the_capture_does_not_know_stays_unpinned(self):
        registry = reg(city='גבעת ברנר')
        self.assertEqual(geo.seed(registry), 0)
        self.assertEqual((registry['v_x']['lat'], registry['v_x']['drive_min']), (None, None))

    def test_a_venue_with_no_city_is_not_seeded(self):
        registry = reg(city='')
        self.assertEqual(geo.seed(registry), 0)
        self.assertEqual(registry['v_x']['coords_source'], 'unresolved')

    def test_the_spelling_of_the_city_does_not_decide_whether_it_is_seeded(self):
        registry = reg(city='תל אביב-יפו')
        self.assertEqual(geo.seed(registry), 1)
        self.assertEqual(registry['v_x']['drive_min'], 29)
