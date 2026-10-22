import json, re, tempfile, unittest
from tools.getup import classify

def rec(title='ערב ג׳אז', tags=()):
    return {'id': 'x', 'title': title, 'desc': 'ערב ג׳אז אינטימי', 'tags': list(tags),
            'source': {'class': 'ticketing', 'name': 'leaan'}, 'venue_id': 'v'}

class VocabTest(unittest.TestCase):
    def test_the_vocabulary_matches_the_client_character_for_character(self):
        js = open('src/chips.js', encoding='utf-8').read()
        for axis in ('scene', 'crowd', 'format'):
            block = re.search(rf"{axis}: \[(.*?)\]", js, re.S).group(1)
            self.assertEqual(set(re.findall(r"'([^']+)'", block)), set(classify.VOCAB[axis]), axis)
        self.assertIn('מופע מחווה', classify.VOCAB['scene'])
        self.assertIn('להט״ב', classify.VOCAB['crowd'])
        self.assertIn('dj_set', classify.VOCAB['format'])

class LabelTest(unittest.TestCase):
    def test_an_unlisted_label_is_dropped_not_invented(self):
        out = classify.sanitize({'format': 'opera', 'scene': ['אופרה', 'ג׳אז'],
                                 'crowd': ['VIP', '30+', '30+']})
        self.assertEqual(out, {'format': 'unknown', 'scene': ['ג׳אז'], 'crowd': ['30+']})

    def test_only_uncached_titles_are_pending_and_a_cached_one_is_reused(self):
        first = rec('MADONNA THE TRIBUTE SHOW')
        self.assertEqual([p['key'] for p in classify.pending([first], {})], [classify.key(first)])
        labels = classify.merge({}, [{'key': classify.key(first), 'format': 'tribute',
                                      'scene': ['פופ'], 'crowd': []}])
        self.assertEqual(classify.pending([first], labels), [])
        [applied] = classify.apply([first], labels)
        self.assertEqual((applied['format'], applied['scene']), ('tribute', ['פופ']))

    def test_punctuation_does_not_fork_the_cache(self):
        self.assertEqual(classify.key(rec('ערב-ג׳אז')), classify.key(rec('ערב ג׳אז')))

    def test_without_a_label_the_source_categories_decide(self):
        [applied] = classify.apply([rec(tags=['בידור וסטנדאפ'])], {})
        self.assertEqual((applied['format'], applied['scene']), ('standup', ['סטנדאפ']))
        [applied] = classify.apply([rec(tags=['הצגות והרצאות'])], {})
        self.assertEqual((applied['format'], applied['scene']), ('theatre', ['תיאטרון']))
        [applied] = classify.apply([rec(tags=[])], {})
        self.assertEqual((applied['format'], applied['scene'], applied['crowd']), ('unknown', [], []))

    def test_the_cache_round_trips_sorted(self):
        with tempfile.TemporaryDirectory() as root:
            labels = {'b' * 16: {'format': 'unknown', 'scene': [], 'crowd': []},
                      'a' * 16: {'format': 'dj_set', 'scene': ['אלקטרונית/טכנו'], 'crowd': []}}
            self.assertTrue(classify.save(root, labels))
            self.assertFalse(classify.save(root, labels))
            self.assertEqual(list(json.load(open(f'{root}/data/labels.json', encoding='utf-8'))),
                             ['a' * 16, 'b' * 16])
