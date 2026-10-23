import json, os, tempfile, unittest
from tools.getup import venues

ROOT = '.'


def registry(**city):
    """A tiny registry with one hall per city, so name-only identity can be exercised."""
    out = {}
    for name, place in city.items():
        vid = 'v_' + name
        out[vid] = {'id': vid, 'name': f'היכל התרבות, {place}', 'aliases': [],
                    'city': place, 'lat': None, 'lon': None, 'drive_min': None,
                    'coords_source': 'unresolved', 'tier': 'mid', 'parking': None,
                    'access': None, 'transport': None,
                    'social': {'instagram': None, 'facebook': None}}
    return out


class CityTest(unittest.TestCase):
    def test_the_observed_spellings_collapse_to_one_city(self):
        self.assertEqual(venues.norm_city('קרית ביאליק'), venues.norm_city('קריית ביאליק'))
        self.assertEqual(venues.norm_city('מודיעין'), venues.norm_city('מודיעין מכבים רעות'))
        self.assertEqual(venues.norm_city('תל אביב-יפו'), venues.norm_city('תל אביב'))
        self.assertEqual(venues.norm_city('איירפורט סיטי'), venues.norm_city('נתב"ג'))
        self.assertEqual(venues.norm_city('קרית שדה התעופה'), venues.norm_city('נתב"ג'))
        self.assertEqual(venues.norm_city('פתח תקוה'), venues.norm_city('פתח תקווה'))

    def test_a_missing_city_is_the_empty_string(self):
        self.assertEqual(venues.norm_city(None), '')
        self.assertEqual(venues.norm_city('   '), '')

    def test_a_street_in_the_city_slot_is_not_a_city(self):
        self.assertEqual(venues.norm_city('שדרות שאול המלך 2 בתל אביב'), '')
        self.assertEqual(venues.norm_city('2254'), '')


class NameTest(unittest.TestCase):
    def test_punctuation_and_niqud_only_survive_the_loose_form(self):
        self.assertEqual(venues.norm_name('  מועדון   ״הבימה״ '), 'מועדון "הבימה"')
        self.assertEqual(venues.norm_name_loose('מועדון ״הבימה״'), 'מועדון הבימה')
        self.assertEqual(venues.norm_name_loose('ג׳אז-בר'), venues.norm_name_loose('גאז בר'))

    def test_a_parenthetical_hall_is_not_erased_by_the_loose_form(self):
        # an "אולם 1" and an "אולם 2" in one building are two halls, not one
        self.assertNotEqual(venues.norm_name_loose('היכל התרבות (אולם 1)'),
                            venues.norm_name_loose('היכל התרבות (אולם 2)'))
        self.assertNotEqual(venues.norm_name_loose('תיאטרון חולון (אולם 2)'),
                            venues.norm_name_loose('תיאטרון חולון (אולם 3)'))
        # the word "hall" is filler, the room it names is the identity
        self.assertEqual(venues.norm_name_loose('בית ציוני אמריקה (אולם מאירהוף)'),
                         venues.norm_name_loose('בית ציוני אמריקה (מאירהוף)'))
        self.assertEqual(venues.norm_name_loose('היכל התרבות (אולם 1)'),
                         'היכל התרבות 1')

    def test_the_two_spellings_of_קרית_in_a_hall_name_are_one_key(self):
        self.assertEqual(venues.norm_name('היכל ספי ריבלין, קרית השרון, נתניה'),
                         venues.norm_name('היכל ספי ריבלין, קריית השרון, נתניה'))

    def test_a_city_suffix_leaves_only_when_the_tail_is_a_known_city(self):
        self.assertEqual(venues.strip_city_suffix('בית ציוני אמריקה (מאירהוף), תל אביב', 'תל אביב'),
                         'בית ציוני אמריקה (מאירהוף)')
        self.assertEqual(venues.strip_city_suffix('היכל התרבות, כפר סבא', None), 'היכל התרבות')
        self.assertEqual(venues.strip_city_suffix('אולם בר-אוריין, קשת אילון', None),
                         'אולם בר-אוריין, קשת אילון')
        self.assertEqual(venues.strip_city_suffix('תיאטרון גבעתיים', None), 'תיאטרון גבעתיים')


class ResolveTest(unittest.TestCase):
    def setUp(self):
        self.reg = venues.load(ROOT)

    def test_one_hall_name_resolves_per_city(self):
        rishon = venues.resolve(self.reg, 'היכל התרבות', 'ראשון לציון')
        petah = venues.resolve(self.reg, 'היכל התרבות', 'פתח תקוה')
        self.assertEqual(rishon, 'v_heichal_tarbut_rishon')
        self.assertEqual(petah, 'v_heichal_tarbut_petah_tikva')   # spelling collapse
        self.assertNotEqual(rishon, petah)

    def test_a_city_suffix_in_the_source_name_still_resolves(self):
        self.assertEqual(venues.resolve(self.reg, 'היכל התרבות, פתח תקווה', 'פתח תקווה'),
                         'v_heichal_tarbut_petah_tikva')

    def test_an_alias_resolves_to_its_venue(self):
        self.assertEqual(venues.resolve(self.reg, 'Zionist America House', 'תל אביב'),
                         'v_zionist_america_tlv')
        self.assertEqual(venues.resolve(self.reg, 'היכל התרבות ספי ריבלין, קריית השרון', 'נתניה'),
                         'v_heichal_spi_rivlin_netanya')

    def test_a_city_suffix_on_the_source_venue_does_not_create_a_second_venue(self):
        with_suffix = venues.resolve(self.reg, 'בית ציוני אמריקה (מאירהוף), תל אביב', 'תל אביב')
        bare = venues.resolve(self.reg, 'בית ציוני אמריקה (מאירהוף)', 'תל אביב')
        self.assertEqual(with_suffix, bare)
        self.assertTrue(with_suffix.startswith('v_'))

    def test_punctuation_and_parentheses_are_only_a_second_try(self):
        first = venues.resolve(self.reg, 'מועדון ״הבימה״', 'תל אביב')
        second = venues.resolve(self.reg, 'מועדון הבימה', 'תל אביב')
        self.assertEqual(first, second)

    def test_an_unseen_venue_gets_one_stable_provisional_entry(self):
        a = venues.resolve(self.reg, 'מועדון חדש לגמרי', 'חיפה')
        b = venues.resolve(self.reg, 'מועדון חדש לגמרי', 'חיפה')
        self.assertEqual(a, b)
        self.assertTrue(a.startswith('v_'))
        self.assertEqual(self.reg[a]['tier'], 'room')       # never major: no alarm noise
        self.assertIsNone(self.reg[a]['lat'])               # flagged, not silently pinned
        self.assertEqual(self.reg[a]['city'], 'חיפה')
        self.assertEqual(self.reg[a]['coords_source'], 'unresolved')

    def test_a_bare_street_with_a_city_still_has_identity(self):
        self.assertIsNotNone(venues.resolve(self.reg, 'Nisim Elkayam St 10', 'באר שבע'))

    def test_no_name_and_no_city_is_no_venue(self):
        self.assertIsNone(venues.resolve(self.reg, None, None))
        self.assertIsNone(venues.resolve(self.reg, '   ', ''))

    def test_a_name_with_no_city_uses_the_one_hall_the_registry_knows(self):
        # a local registry: the live one now holds this name in more than one city
        reg = {'v_beit_yad_labanim_raanana': {
            'id': 'v_beit_yad_labanim_raanana', 'name': 'בית יד לבנים, רעננה', 'aliases': [],
            'city': 'רעננה', 'lat': None, 'lon': None, 'drive_min': None,
            'coords_source': 'unresolved', 'tier': 'room', 'parking': None,
            'access': None, 'transport': None,
            'social': {'instagram': None, 'facebook': None}}}
        self.assertEqual(venues.resolve(reg, 'בית יד לבנים', None),
                         'v_beit_yad_labanim_raanana')

    def test_a_city_named_inside_the_venue_string_is_the_city(self):
        self.assertEqual(venues.resolve(self.reg, 'בית יד לבנים, רעננה', None),
                         'v_beit_yad_labanim_raanana')
        vid = venues.resolve(self.reg, 'בית יד לבנים, אשדוד', None)
        self.assertNotEqual(vid, 'v_beit_yad_labanim_raanana')
        self.assertEqual(self.reg[vid]['city'], 'אשדוד')

    def test_a_name_known_in_several_cities_is_not_guessed_from_the_name_alone(self):
        reg = registry(haifa='חיפה', netanya='נתניה')
        vid = venues.resolve(reg, 'היכל התרבות', None)
        self.assertNotIn(vid, ('v_haifa', 'v_netanya'))
        self.assertEqual(reg[vid]['city'], '')
        self.assertEqual(reg[vid]['name'], 'היכל התרבות')

    def test_a_draft_with_a_city_never_borrows_a_hall_from_another_city(self):
        reg = venues.load(ROOT)
        vid = venues.resolve(reg, 'בית יד לבנים', 'אשדוד')
        self.assertNotEqual(vid, 'v_beit_yad_labanim_raanana')
        self.assertEqual(reg[vid]['city'], 'אשדוד')

    def test_an_unknown_city_is_stored_as_no_city(self):
        vid = venues.resolve(self.reg, 'מועדון בלי עיר', 'שדרות שאול המלך 2 בתל אביב')
        self.assertEqual(self.reg[vid]['city'], '')
        self.assertEqual(venues.resolve(self.reg, 'מועדון בלי עיר', None), vid)

    def test_a_locality_that_is_not_a_city_stays_in_the_name(self):
        vid = venues.resolve(self.reg, 'אולם בר-אוריין, קשת אילון', None)
        self.assertEqual(self.reg[vid]['name'], 'אולם בר-אוריין, קשת אילון')
        self.assertEqual(self.reg[vid]['city'], '')

    def test_two_parenthetical_halls_in_one_city_keep_two_ids(self):
        reg = {vid: {'id': vid, 'name': f'היכל התרבות (אולם {n})', 'aliases': [],
                     'city': 'חולון', 'lat': None, 'lon': None, 'drive_min': None,
                     'coords_source': 'unresolved', 'tier': 'room', 'parking': None,
                     'access': None, 'transport': None,
                     'social': {'instagram': None, 'facebook': None}}
               for vid, n in (('v_one', 1), ('v_two', 2))}
        self.assertEqual(venues.resolve(reg, 'היכל התרבות (אולם 1)', 'חולון'), 'v_one')
        self.assertEqual(venues.resolve(reg, 'היכל התרבות (אולם 2)', 'חולון'), 'v_two')
        self.assertEqual(len(reg), 2)                    # nothing merged, nothing provisioned

    def test_a_loose_key_two_halls_share_is_not_identity(self):
        reg = {vid: {'id': vid, 'name': name, 'aliases': [], 'city': 'חולון',
                     'lat': None, 'lon': None, 'drive_min': None,
                     'coords_source': 'unresolved', 'tier': 'room', 'parking': None,
                     'access': None, 'transport': None,
                     'social': {'instagram': None, 'facebook': None}}
               for vid, name in (('v_one', 'היכל ״התרבות״'), ('v_two', 'היכל התרבות'))}
        # the loose form says these are one name; the registry says they are two halls
        self.assertNotIn((venues.norm_name_loose('היכל התרבות'), 'חולון'),
                         venues.alias_index(reg))
        vid = venues.resolve(reg, 'היכל התרבות!', 'חולון')
        self.assertNotIn(vid, ('v_one', 'v_two'))        # ambiguous: provisional, never a pick
        self.assertEqual(reg['v_one']['name'], 'היכל ״התרבות״')   # the entries stay untouched
        self.assertEqual(reg['v_two']['name'], 'היכל התרבות')

    def test_an_unrecognised_city_spelling_borrows_the_one_hall_with_that_name(self):
        reg = {vid: {'id': vid, 'name': name, 'aliases': [], 'city': 'מעלות תרשיחא',
                     'lat': None, 'lon': None, 'drive_min': None,
                     'coords_source': 'unresolved', 'tier': 'room', 'parking': None,
                     'access': None, 'transport': None,
                     'social': {'instagram': None, 'facebook': None}}
               for vid, name in (('v_hall', 'היכל התרבות, מעלות תרשיחא'),)}
        self.assertEqual(venues.resolve(reg, 'היכל התרבות', 'מעלו תרשיחא'), 'v_hall')
        self.assertEqual(len(reg), 1)                    # one hall, one city, one entry

    def test_an_unknown_city_with_no_name_match_still_provisions(self):
        vid = venues.resolve(self.reg, 'מועדון חדש לגמרי', 'מעלו תרשיחא')
        self.assertTrue(vid.startswith('v_'))
        self.assertEqual(self.reg[vid]['city'], 'מעלו תרשיחא')

    def test_a_spelling_variant_of_a_registry_name_does_not_create_a_second_hall(self):
        vid = venues.resolve(self.reg, 'היכל ספי ריבלין, קריית השרון, נתניה', 'נתניה')
        self.assertEqual(vid, 'v_heichal_spi_rivlin_netanya')


class FindTest(unittest.TestCase):
    def test_find_answers_without_provisioning(self):
        reg = venues.load('.')
        before = len(reg)
        self.assertEqual(venues.find(reg, 'בית ציוני אמריקה (מאירהוף)', 'תל אביב'),
                         'v_zionist_america_tlv')
        self.assertIsNone(venues.find(reg, 'מועדון שלא קיים', 'חיפה'))
        self.assertEqual(len(reg), before)          # a prefs lookup must never curate the registry


class CityInNameTest(unittest.TestCase):
    """A city the source put in the venue name instead of the city slot."""

    def resolve(self, name, city=None):
        reg = {}
        return reg, venues.resolve(reg, name, city)

    def test_a_trailing_city_in_the_venue_name_is_the_city(self):
        for name, place in (('זאפה תל אביב', 'תל אביב'),
                            ('צוותא תל אביב', 'תל אביב'),
                            ('בית יד לבנים רמת השרון', 'רמת השרון')):
            reg, vid = self.resolve(name)
            self.assertEqual(reg[vid]['city'], place, name)
            self.assertEqual(reg[vid]['name'], name)     # published name keeps the city

    def test_a_venue_with_no_city_in_its_name_stays_unpinned(self):
        reg, vid = self.resolve('היכל התרבות')
        self.assertEqual(reg[vid]['city'], '')
        self.assertIsNone(reg[vid]['lat'])
        self.assertEqual(reg[vid]['coords_source'], 'unresolved')

    def test_a_tail_that_is_not_a_known_city_is_still_not_a_city(self):
        reg, vid = self.resolve('אולם בר-אוריין, קשת אילון')
        self.assertEqual(reg[vid]['name'], 'אולם בר-אוריין, קשת אילון')
        self.assertEqual(reg[vid]['city'], '')

    def test_an_explicit_city_is_not_overridden_by_the_name(self):
        reg, vid = self.resolve('זאפה תל אביב', 'חיפה')
        self.assertEqual(reg[vid]['city'], 'חיפה')


class RegistryTest(unittest.TestCase):
    def test_the_registry_city_wins_and_the_draft_city_is_the_fallback(self):
        reg = venues.load(ROOT)
        self.assertEqual(venues.city_of(reg, 'v_ozen_tlv', 'אשדוד'), 'תל אביב')
        self.assertEqual(venues.city_of(reg, 'v_missing', 'אשדוד'), 'אשדוד')
        self.assertIsNone(venues.city_of(reg, 'v_missing', None))

    def test_a_saved_registry_is_the_same_bytes_the_second_time(self):
        reg = venues.load(ROOT)
        with tempfile.TemporaryDirectory() as root:
            self.assertTrue(venues.save(root, reg))
            path = f'{root}/venue/venues.json'
            with open(path, 'rb') as f:
                first = f.read()
            self.assertFalse(venues.save(root, reg))
            with open(path, 'rb') as f:
                self.assertEqual(f.read(), first)
            self.assertEqual(json.loads(first), reg)

    def test_the_alias_index_carries_the_cityless_base_of_every_name(self):
        index = venues.alias_index(venues.load(ROOT))
        self.assertEqual(index[(venues.norm_name('היכל התרבות'), 'פתח תקווה')],
                         'v_heichal_tarbut_petah_tikva')
        self.assertEqual(index[(venues.norm_name_loose('היכל התרבות ספי ריבלין, קריית השרון'),
                                'נתניה')], 'v_heichal_spi_rivlin_netanya')


class LoadTest(unittest.TestCase):
    def test_a_missing_registry_is_empty_not_a_crash(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(venues.load(root), {})

    def test_a_corrupt_registry_refuses_instead_of_erasing_curation(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(f'{root}/venue')
            with open(f'{root}/venue/venues.json', 'w') as f:
                f.write('{')
            with self.assertRaises(ValueError) as caught:
                venues.load(root)
            self.assertIn('venues.json', str(caught.exception))

    def test_a_registry_that_is_not_an_object_refuses(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(f'{root}/venue')
            with open(f'{root}/venue/venues.json', 'w') as f:
                f.write('[]')
            with self.assertRaises(ValueError):
                venues.load(root)
