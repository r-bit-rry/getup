import os, unittest
from tools.getup import scan
from tools.getup.adapters import biluim

CAPTURE = 'docs/research/2026-10-22/biluim-tlv-excerpt.html'
REAL = open(CAPTURE, encoding='utf-8').read()
HREF = [
    '/events/e/44568-%D7%90%D7%9E%D7%A8%D7%92%D7%9D-%D7%9C%D7%99%D7%99%D7%9F-%D7%94%D7%92%D7%9D-%D7%A9%D7%9C-%D7%90%D7%9C%D7%99',
    '/events/e/61791-%D7%94%D7%9C%D7%9C%D7%95%D7%99%D7%94-%D7%9C%D7%A2%D7%95%D7%9C%D7%9D-%D7%A7%D7%95%D7%91%D7%99-%D7%90%D7%A9%D7%A8%D7%AA',
    '/events/e/1395-%D7%92%D7%99%D7%90-%D7%9E%D7%99%D7%A0%D7%98%D7%95%D7%A1-%D7%98%D7%A8%D7%99%D7%95-%D7%9E%D7%A1%D7%A2-%D7%91%D7%99%D7%9F-%D7%A2%D7%95%D7%9C%D7%9E%D7%95%D7%AA',
]

# The shape the skill used to document; the live page has no <li>, so it is a shape-change negative.
STALE = '''<ul class="events"><li class="event">
  <a href="/event/123" class="title">ערב ג׳אז בבית יד לבנים</a>
  <span class="venue">בית יד לבנים</span><span class="city">רעננה</span>
  <time datetime="2026-10-29T20:30">29.10</time>
  <span class="price">₪80</span><p class="desc">רביעיית ג׳אז</p></li></ul>'''

class BiluimTest(unittest.TestCase):
    def test_the_three_real_cards_carry_every_served_field(self):
        drafts = biluim.parse(REAL)
        self.assertEqual([d['source_id'] for d in drafts], HREF)
        first, second, third = drafts
        self.assertEqual((first['source'], first['class']), ('biluim', 'aggregator'))
        self.assertEqual(first['title'], "אמרג'ם, ליין הג'ם של אלי")
        self.assertEqual(first['venue'], 'לבונטין 7')
        self.assertIsNone(first['price_from'])
        self.assertEqual(second['title'], 'הללויה לעולם -קובי אשרת')
        self.assertEqual(second['venue'], 'תיאטרון גבעתיים')
        self.assertEqual((second['price_from'], second['price_max']), (90, 110))
        self.assertEqual(third['title'], 'גיא מינטוס טריו: מסע בין עולמות')
        self.assertEqual(third['venue'], 'אולם בר-אוריין, קשת אילון')
        self.assertEqual((third['price_from'], third['price_max']), (80, 95))
        for draft in drafts:
            self.assertEqual(draft['start'], 1792688400)   # 2026-10-22 20:00 Asia/Jerusalem
            self.assertEqual((draft['city'], draft['street'], draft['desc']), (None, None, None))
            self.assertEqual(draft['tags'], ['הופעה'])
            self.assertEqual(draft['url'], biluim.BASE + draft['source_id'])

    def test_a_void_tag_inside_a_card_does_not_swallow_the_rest(self):
        flooded = REAL.replace('<h3 class="font-extrabold', '<br><h3 class="font-extrabold', 1)
        self.assertEqual(len(biluim.parse(flooded)), 3)

    def test_the_old_li_event_shape_warns_and_yields_nothing(self):
        with self.assertLogs('getup', level='WARNING') as logs:
            self.assertEqual(biluim.parse(STALE), [])
        self.assertIn('biluim', logs.output[0])

    def test_the_excerpt_is_installed_as_the_cassette(self):
        drafts, counts, failures, status = scan.scan_from_dir(['biluim'], 'docs/research/2026-10-22')
        self.assertEqual((len(drafts), counts, failures, status),
                         (3, {'biluim': 3}, [], {'biluim': 'ok'}))

@unittest.skipUnless(os.environ.get('GETUP_LIVE') == '1', 'live source; set GETUP_LIVE=1')
class BiluimLiveTest(unittest.TestCase):
    def test_the_listing_still_answers_with_cards(self):
        drafts, counts, failures, status = scan.scan(['biluim'])
        self.assertEqual((failures, status), ([], {'biluim': 'ok'}))
        self.assertGreater(counts['biluim'], 0)
