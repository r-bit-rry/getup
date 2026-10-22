import unittest
from tools.getup import geo, normalize

DRAFT = {'source': 'leaan', 'class': 'ticketing', 'source_id': 'a1', 'title': 'ערב ג׳אז',
         'venue': 'אוזן בר', 'venue_id': 'v_ozen_tlv', 'city': 'תל אביב', 'street': '',
         'start': 1792780200, 'end': 1792787400, 'price_from': 129, 'price_max': None,
         'soldout': False, 'desc': 'ג׳אז  חופשי', 'url': 'https://x', 'tags': ['ג׳אז'],
         'lat': 32.0771, 'lon': 34.7753, 'drive_min': 29}

KEYS = {'id', 'day', 'start', 'end', 'title', 'venue_id', 'city', 'price_from',
        'price_max', 'soldout', 'free', 'free_until', 'desc', 'source', 'urls', 'notes',
        'enrichment', 'seen', 'tags', 'lat', 'lon', 'drive_min', 'drive_approx'}


class TitleTest(unittest.TestCase):
    def test_punctuation_and_emoji_do_not_make_two_titles(self):
        self.assertEqual(normalize.norm_title('סוף סיפור- סוף מסלול כפיר 🦁'),
                         normalize.norm_title('סוף סיפור סוף מסלול כפיר'))
        self.assertEqual(normalize.norm_title('  ערב   ג׳אז '), normalize.norm_title('ערב ג׳אז'))

    def test_a_geresh_does_not_split_the_word(self):
        # the rule: a geresh/gershayim is deleted, never turned into a word break
        self.assertEqual(normalize.norm_title('ג׳אז'), normalize.norm_title('גאז'))
        self.assertEqual(normalize.norm_title('ערב ג׳אז'), 'ערב גאז')
        self.assertEqual(normalize.norm_title('להט״ב'), normalize.norm_title('להטב'))

    def test_case_and_niqqud_are_not_identity(self):
        self.assertEqual(normalize.norm_title('MADONNA — The Tribute'),
                         normalize.norm_title('madonna the tribute'))
        self.assertEqual(normalize.norm_title('הֶפְסֵק'), normalize.norm_title('הפסק'))


class BucketTest(unittest.TestCase):
    def test_after_midnight_belongs_to_the_previous_day(self):
        self.assertEqual(normalize.bucket_day(1792780200), '2026-10-23')  # 21:30
        self.assertEqual(normalize.bucket_day(1792796400), '2026-10-23')  # 02:00 next day
        self.assertEqual(normalize.bucket_day(1792810740), '2026-10-23')  # 05:59
        self.assertEqual(normalize.bucket_day(1792810800), '2026-10-24')  # 06:00

    def test_winter_time_is_not_a_fixed_offset(self):
        # 2026-11-05 05:30 IST; a +03:00 shortcut would read 06:30 and keep it on the 5th
        self.assertEqual(normalize.bucket_day(1793849400), '2026-11-04')

    def test_the_served_horizon_is_exactly_thirty_dates(self):
        days = normalize.horizon('2026-10-23')
        self.assertEqual(normalize.SERVE_DAYS, 30)
        self.assertEqual(len(days), 30)
        self.assertEqual((days[0], days[-1]), ('2026-10-23', '2026-11-21'))


class RecordTest(unittest.TestCase):
    def test_the_id_is_what_the_client_would_have_synthesized(self):
        rec = normalize.record(dict(DRAFT))
        self.assertEqual(rec['id'], 'v_ozen_tlv|2026-10-23|21:30')
        self.assertEqual(normalize.id_for('v_ozen_tlv', '2026-10-23', 1792780200), rec['id'])

    def test_the_record_holds_exactly_the_fields_the_client_reads(self):
        self.assertEqual(set(normalize.record(dict(DRAFT))), KEYS)

    def test_source_categories_stay_internal_and_coordinates_pass_through(self):
        rec = normalize.record(dict(DRAFT))
        self.assertEqual(rec['tags'], ['ג׳אז'])          # stripped by write, used by classify
        self.assertEqual((rec['lat'], rec['lon'], rec['drive_min']), (32.0771, 34.7753, 29))
        self.assertEqual(rec['source'], {'class': 'ticketing', 'name': 'leaan'})
        self.assertEqual(rec['urls'], {'tickets': 'https://x', 'community': None,
                                       'source': 'https://x'})

    def test_only_a_city_centroid_minute_is_marked_approximate(self):
        self.assertIs(normalize.record(dict(DRAFT))['drive_approx'], False)
        self.assertIs(normalize.record({**DRAFT, 'coords_source': 'nominatim'})['drive_approx'],
                      False)
        self.assertIs(normalize.record({**DRAFT, 'coords_source': geo.SHORTCUT})['drive_approx'],
                      True)
        # a junk value is False, never a truthy leak into the client
        self.assertIs(normalize.record({**DRAFT, 'coords_source': 'yes'})['drive_approx'], False)

    def test_a_community_source_has_no_ticket_link(self):
        rec = normalize.record({**DRAFT, 'class': 'nightlife'})
        self.assertEqual(rec['urls'], {'tickets': None, 'community': None,
                                       'source': 'https://x'})

    def test_an_event_whose_venue_has_no_point_keeps_null_coordinates(self):
        rec = normalize.record({**DRAFT, 'venue_id': 'v_new', 'lat': None, 'lon': None,
                                'drive_min': None})
        self.assertEqual((rec['lat'], rec['lon'], rec['drive_min']), (None, None, None))

    def test_an_absent_venue_id_is_dropped_with_one_warning(self):
        for bad in (None, '', '   ', 17):
            with self.assertLogs('getup', level='WARNING') as logs:
                self.assertIsNone(normalize.record({**DRAFT, 'venue_id': bad}))
            self.assertEqual(len(logs.output), 1)
            self.assertIn('a1', logs.output[0])

    def test_an_absurd_or_missing_start_is_dropped_with_one_warning(self):
        for bad in (None, 0, 1e16, '1792780200', -1, 4102444801):
            with self.assertLogs('getup', level='WARNING') as logs:
                self.assertIsNone(normalize.record({**DRAFT, 'start': bad}), str(bad))
            self.assertEqual(len(logs.output), 1)
            self.assertIn('a1', logs.output[0])

    def test_an_empty_title_is_dropped(self):
        with self.assertLogs('getup', level='WARNING'):
            self.assertIsNone(normalize.record({**DRAFT, 'title': '   '}))

    def test_an_end_five_months_later_is_not_a_show_end(self):
        # the real capture's first record ends on 2026-11-01 for a June start
        rec = normalize.record({**DRAFT, 'start': 1780988400, 'end': 1793469600})
        self.assertIsNone(rec['end'])
        self.assertEqual(rec['start'], 1780988400)

    def test_a_show_that_ends_soon_keeps_its_end(self):
        self.assertEqual(normalize.record(dict(DRAFT))['end'], 1792787400)
        self.assertIsNone(normalize.record({**DRAFT, 'end': DRAFT['start']})['end'])

    def test_a_long_description_is_capped_at_600_and_loses_no_whole_word(self):
        text = ('מילה ' * 400).strip()
        out = normalize.desc_cap(text)
        self.assertLessEqual(len(out), 601)
        self.assertTrue(out.endswith('…'))
        self.assertEqual(normalize.desc_cap('  א  ב \n ג '), 'א ב ג')
        self.assertEqual(normalize.desc_cap('א' * 800), 'א' * 600 + '…')

    def test_a_zero_price_is_free_and_an_unknown_price_is_not(self):
        self.assertTrue(normalize.record({**DRAFT, 'price_from': 0})['free'])
        self.assertFalse(normalize.record({**DRAFT, 'price_from': None})['free'])
        self.assertIsNone(normalize.record({**DRAFT, 'price_from': None})['price_from'])

    def test_a_price_that_arrived_as_text_is_a_number(self):
        rec = normalize.record({**DRAFT, 'price_from': '129', 'price_max': '₪250'})
        self.assertEqual((rec['price_from'], rec['price_max']), (129, None))

    def test_a_non_finite_price_never_reaches_the_bytes(self):
        rec = normalize.record({**DRAFT, 'price_from': float('nan'), 'price_max': float('inf')})
        self.assertEqual((rec['price_from'], rec['price_max']), (None, None))

    def test_soldout_is_a_bool(self):
        self.assertIs(normalize.record({**DRAFT, 'soldout': None})['soldout'], False)
        self.assertIs(normalize.record({**DRAFT, 'soldout': True})['soldout'], True)

    def test_a_draft_that_is_not_an_object_is_dropped_not_a_crash(self):
        for bad in (None, 'x', []):
            with self.assertLogs('getup', level='WARNING'):
                self.assertIsNone(normalize.record(bad))
