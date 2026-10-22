import unittest
from datetime import datetime, timezone
from tools.getup.adapters import popit

XML = open('docs/research/2026-10-21/popit.xml', encoding='utf-8').read()

def drafts():
    return {d['source_id']: d for d in popit.parse(XML)}

def one(title, desc):
    payload = ('<rss><channel><item>' + f'<title>{title}</title><guid>1</guid>'
               '<pubDate>Sat, 03 Oct 2026 00:16:40 GMT</pubDate>'
               f'<description>{desc}</description></item></channel></rss>')
    return popit.parse(payload)[0]

class PopitTest(unittest.TestCase):
    def test_a_real_item_carries_venue_city_clock_and_its_slug_url(self):
        d = drafts()['2315']                              # "…ב-14 בנובמבר בשעה 14:00"
        self.assertEqual(d['class'], 'nightlife')
        self.assertEqual((d['venue'], d['city']), ('Altalena St 8', 'ראשון לציון'))
        self.assertEqual(d['start'], 1794657600)          # 2026-11-14 14:00 Asia/Jerusalem
        self.assertEqual(d['url'], 'https://popit.events/event/urban-music-14-11-2315')
        self.assertNotEqual(d['url'], 'https://popit.events/event/2315')

    def test_the_publication_date_is_never_used_as_the_start(self):
        # 2303 was published 2026-10-19 and starts 2026-10-24 22:00, five days later
        published = 1792426896                               # 2026-10-19T16:21:36Z
        self.assertGreater(drafts()['2303']['start'], published + 86400)

    def test_an_item_with_no_clock_has_no_start_rather_than_a_guess(self):
        self.assertIsNone(drafts()['2309']['start'])       # "ב-21 באוקטובר" with no שעה

    def test_a_street_suffix_is_the_venue(self):
        d = drafts()['2303']                              # no place clause, "— ברוך קטינקא 2"
        self.assertEqual(d['venue'], 'ברוך קטינקא 2')
        self.assertEqual(d['start'], 1792868400)          # 2026-10-24 22:00

    def test_an_english_place_suffix_is_mapped_to_hebrew(self):
        self.assertEqual(popit.place_from_title('DARWISH — Tel Aviv Port'),
                         ('נמל תל אביב', 'תל אביב'))

    def test_a_city_suffix_gives_a_city_and_never_invents_a_venue(self):
        self.assertEqual(popit.place_from_title('FUEGO — Tel Aviv-Yafo'), (None, 'תל אביב'))

    def test_an_unknown_location_keeps_the_title_and_names_no_venue(self):
        d = drafts()['2263']                              # "— Israel (מיקום לא ידוע)"
        self.assertIsNone(d['venue'])
        self.assertIsNone(d['city'])
        self.assertIn('מיקום לא ידוע', d['title'])        # not consumed, so the suffix stays

    def test_a_consumed_place_suffix_leaves_the_title(self):
        self.assertEqual(drafts()['2315']['title'], 'Urban Music 14/11')
        self.assertEqual(drafts()['2229']['title'], 'SILVESTER ROOFTOP CELEBRATION (30+)')

    def test_midnight_prose_is_not_a_clock(self):
        self.assertIsNone(drafts()['2229']['start'])       # "ב-31 בדצמבר" + בחצות, no שעה

    def test_a_street_in_the_city_slot_is_not_a_city(self):
        d = drafts()['2254']
        self.assertEqual(d['venue'], 'מועדון אטלנטה')
        self.assertIsNone(d['city'])

    def test_the_venue_starts_at_the_body_after_the_party_phrase(self):
        d = one('סילבסטר', 'מסיבת סילבסטר היא מסיבת מיינסטרים במרכז ביאליק, קרית ביאליק, '
                           'ב-31 בדצמבר בשעה 21:00')
        self.assertEqual((d['venue'], d['city']), ('מרכז ביאליק', 'קרית ביאליק'))

    def test_a_month_that_wraps_into_january_belongs_to_the_next_year(self):
        published = datetime(2026, 12, 30, 12, tzinfo=timezone.utc)
        self.assertEqual(popit.parse_hebrew_when('מסיבה ב-2 בינואר בשעה 23:00', published),
                         1798923600)                    # 2027-01-02 23:00 Asia/Jerusalem

    def test_exactly_six_months_behind_rolls_the_year(self):
        published = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
        self.assertEqual(popit.parse_hebrew_when('מסיבה ב-1 בינואר בשעה 23:00', published),
                         1798837200)                    # 2027-01-01 23:00 Asia/Jerusalem

    def test_a_feed_with_no_items_warns_instead_of_reporting_a_quiet_night(self):
        with self.assertLogs('getup', level='WARNING') as logs:
            self.assertEqual(popit.parse('<rss><channel></channel></rss>'), [])
        self.assertIn('popit', logs.output[0])
