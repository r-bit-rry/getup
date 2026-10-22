import os, unittest
from tools.getup import scan
from tools.getup.adapters import biluim

# A synthetic card in the shape the skill's recipe documents; the real markup is not in the
# capture, so the live test below is what proves the recipe still holds.
HTML = '''<ul class="events"><li class="event">
  <a href="/event/123" class="title">ערב ג׳אז בבית יד לבנים</a>
  <span class="venue">בית יד לבנים</span><span class="city">רעננה</span>
  <time datetime="2026-10-29T20:30">29.10</time>
  <span class="price">₪80</span><p class="desc">רביעיית ג׳אז</p></li></ul>'''

class BiluimTest(unittest.TestCase):
    def test_a_card_becomes_an_aggregator_draft(self):
        [d] = biluim.parse(HTML)
        self.assertEqual(d['class'], 'aggregator')
        self.assertEqual(d['source_id'], '/event/123')
        self.assertEqual((d['venue'], d['city']), ('בית יד לבנים', 'רעננה'))
        self.assertEqual(d['start'], 1793298600)          # 2026-10-29 20:30 Asia/Jerusalem
        self.assertEqual(d['price_from'], 80)
        self.assertEqual(d['desc'], 'רביעיית ג׳אז')

    def test_markup_that_no_longer_matches_warns_and_yields_nothing(self):
        with self.assertLogs('getup', level='WARNING') as logs:
            self.assertEqual(biluim.parse('<html><body><div>new site</div></body></html>'), [])
        self.assertIn('biluim', logs.output[0])

@unittest.skipUnless(os.environ.get('GETUP_LIVE'), 'live source; set GETUP_LIVE=1')
class BiluimLiveTest(unittest.TestCase):
    def test_the_listing_still_answers_with_cards(self):
        drafts, counts, failures, status = scan.scan(['biluim'])
        self.assertEqual((failures, status), ([], {'biluim': 'ok'}))
        self.assertGreater(counts['biluim'], 0)
