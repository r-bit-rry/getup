import tempfile
import unittest

from tools.getup import human, write

DRAFT = {'class': 'human', 'source': 'github', 'title': 'ערב ג׳אז',
         'venue': 'בית ציוני אמריקה (מאירהוף)', 'city': 'תל אביב',
         'start': 1794686400, 'url': 'https://github.com/roy/getup/issues/7',
         'tickets': None, 'community': None, 'price_from': None, 'desc': ''}


class StoreTest(unittest.TestCase):
    def test_a_missing_store_is_empty_and_a_corrupt_one_raises(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(human.load(root), {})
            write.write_json(human.store_file(root), {'7': 'not a draft'})
            with self.assertRaises(ValueError):
                human.load(root)

    def test_put_is_byte_stable_and_one_issue_has_one_draft(self):
        with tempfile.TemporaryDirectory() as root:
            store = human.load(root)
            self.assertTrue(human.put(store, 7, DRAFT))
            self.assertFalse(human.put(store, 7, dict(DRAFT)))
            self.assertTrue(human.put(store, 7, {**DRAFT, 'title': 'תיקון'}))   # a correction replaces
            self.assertTrue(human.save(root, store))
            self.assertFalse(human.save(root, store))
            self.assertEqual(human.load(root)['7']['title'], 'תיקון')

    def test_records_are_drafts_ordered_by_issue_number_not_by_string(self):
        store = {}
        human.put(store, 10, {**DRAFT, 'title': 'b'})
        human.put(store, 2, {**DRAFT, 'title': 'a'})
        self.assertEqual([r['title'] for r in human.records(store)], ['a', 'b'])
        self.assertNotIn('venue_id', human.records(store)[0])


if __name__ == '__main__':
    unittest.main()
