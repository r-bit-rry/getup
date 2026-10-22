import json, unittest
from tools.getup import derive

def rec(**o):
    base = {'id': 'x', 'title': 'ערב', 'venue_id': 'v', 'city': 'תל אביב', 'price_from': 100,
            'format': 'tribute', 'drive_min': 30, 'free_until': None, 'notes': [], 'desc': '',
            'source': {'class': 'ticketing', 'name': 'leaan'}}
    return {**base, **o}

MAJOR = {'v': {'tier': 'major', 'parking': 'חניון מאירהוף, ₪30/שעה',
               'access': 'נגיש לכיסא גלגלים', 'transport': 'קו 5'}}
MID = {'v': {'tier': 'mid', 'parking': None, 'access': None, 'transport': None}}

class P90Test(unittest.TestCase):
    def test_the_real_capture_p90_is_199(self):
        prices = [e['price'] for e in json.load(open('docs/research/2026-10-21/leaan-events.json',
                                                     encoding='utf-8'))]
        self.assertEqual(derive.p90(prices), 199)

    def test_a_ten_price_set_uses_the_nearest_rank(self):
        self.assertEqual(derive.p90([10, 20, 30, 40, 50, 60, 70, 80, 90, 100]), 100)
        self.assertEqual(derive.p90([39]), 39)
        self.assertIsNone(derive.p90([]))

class SignalTest(unittest.TestCase):
    def test_expensive_is_the_run_threshold_or_two_hundred(self):
        set_ = [rec(id=f'r{i}', price_from=p) for i, p in enumerate([39, 49, 59, 69, 79, 89, 99, 129, 149, 199])]
        out = {r['id']: r['expensive'] for r in derive.signals(set_, touring={}, registry=MID)}
        self.assertTrue(out['r9'])       # 199 == p90
        self.assertFalse(out['r7'])      # 129 < 199
        over = derive.signals([rec(price_from=250)], touring={}, registry=MID)
        self.assertTrue(over[0]['expensive'])   # >= 200, even alone
        self.assertFalse(derive.signals([rec(price_from=None)], touring={}, registry=MID)[0]['expensive'])

    def test_commitment_ignores_an_unknown_drive_and_has_no_ticketed_and_48h_clause(self):
        # ticketed, ten days out, 30 minute drive: the amended rule says jump_in
        self.assertEqual(derive.commitment(rec(format='tribute', drive_min=30)), 'jump_in')
        self.assertEqual(derive.commitment(rec(format='tribute', drive_min=None)), 'jump_in')
        self.assertEqual(derive.commitment(rec(format='theatre')), 'plan_ahead')
        self.assertEqual(derive.commitment(rec(format='orchestra')), 'plan_ahead')
        self.assertEqual(derive.commitment(rec(format='festival')), 'plan_ahead')
        self.assertEqual(derive.commitment(rec(format='live_band', drive_min=60)), 'plan_ahead')
        self.assertEqual(derive.commitment(rec(format='live_band', drive_min=59)), 'jump_in')

    def test_notable_needs_a_ticket_seller(self):
        self.assertTrue(derive.notable(rec(), 2, MID))          # touring two cities
        self.assertTrue(derive.notable(rec(price_from=200), 1, MID))
        self.assertFalse(derive.notable(rec(price_from=199), 1, MID))
        self.assertTrue(derive.notable(rec(), 1, MAJOR))         # major venue
        self.assertFalse(derive.notable(rec(source={'class': 'aggregator', 'name': 'biluim'}), 5, MAJOR))

    def test_touring_counts_cities_and_punctuation_does_not_split_a_title(self):
        records = [{'title': e['title'], 'city': e['city']}
                   for e in json.load(open('docs/research/2026-10-21/leaan-events.json', encoding='utf-8'))]
        records.append({'title': 'אסף מור יוסף במופע סטנדאפ!', 'city': 'באר שבע'})
        counts = derive.touring(records)
        self.assertEqual(counts['אסף מור יוסף במופע סטנדאפ'], 15)
        self.assertEqual(sum(1 for n in counts.values() if n >= 2), 30)

    def test_free_until_is_read_from_prose_in_both_languages(self):
        self.assertEqual(derive.free_until('כניסה חינם עד 22:00'), '22:00')
        self.assertEqual(derive.free_until('free before 11pm'), '23:00')
        self.assertIsNone(derive.free_until('כניסה חופשית'))

    def test_venue_facts_reach_the_event_notes_once(self):
        notes = derive.venue_notes(rec(notes=['חניה: חניון מאירהוף, ₪30/שעה']), MAJOR['v'])
        self.assertEqual(notes, ['חניה: חניון מאירהוף, ₪30/שעה', 'נגישות: נגיש לכיסא גלגלים', 'תחבורה: קו 5'])
        self.assertEqual(derive.venue_notes(rec(), None), [])
