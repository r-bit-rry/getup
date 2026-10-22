import json, os, shutil, tempfile, unittest

from tools.getup import intake, venues, write
from tests_py.github_fake import Fake, issue
from tests_py.test_intake_parse import EVENT

TODAY = '2026-10-21'
PREFS = '''### סוג הכלל

לא להציג

### שם המקום

בית ציוני אמריקה (מאירהוף)

### עיר

תל אביב

### אמן או שם מופע

_No response_

### למה

רועש מדי
'''


def fresh(root):
    shutil.copytree('venue', f'{root}/venue')
    os.makedirs(f'{root}/data')


class RuleTest(unittest.TestCase):
    def test_a_venue_rule_resolves_to_an_id_without_touching_the_registry(self):
        reg = venues.load('.')
        spec, problems = intake.prefs_rule(intake.parse_form(PREFS), reg)
        self.assertEqual(problems, [])
        self.assertEqual(spec, {'kind': 'never', 'rule': {'venue_id': 'v_zionist_america_tlv'}})

    def test_an_artist_rule_keeps_the_title_and_both_fields_are_an_and(self):
        fields = intake.parse_form(PREFS)
        self.assertEqual(intake.prefs_rule({**fields, 'שם המקום': '', 'עיר': '',
                                            'אמן או שם מופע': 'The Cure'}, venues.load('.'))[0],
                         {'kind': 'never', 'rule': {'artist': 'The Cure'}})
        both = intake.prefs_rule({**fields, 'אמן או שם מופע': 'The Cure'}, venues.load('.'))
        self.assertEqual(both[0]['rule'], {'venue_id': 'v_zionist_america_tlv', 'artist': 'The Cure'})

    def test_an_unknown_venue_and_an_empty_rule_are_named(self):
        fields = intake.parse_form(PREFS)
        self.assertEqual(intake.prefs_rule({**fields, 'שם המקום': 'מועדון שלא קיים'},
                                           venues.load('.'))[1], ['שם המקום (לא נמצא במאגר)'])
        self.assertEqual(intake.prefs_rule({**fields, 'שם המקום': '', 'עיר': ''},
                                           venues.load('.'))[1], ['שם המקום או אמן'])

    def test_add_rule_keys_the_rule_to_its_issue_and_keeps_the_two_lists(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            write.write_json(intake.prefs_file(root), {'never': [], 'always': []})
            self.assertTrue(intake.add_rule(root, 'never', {'artist': 'The Cure'}, 21))
            self.assertFalse(intake.add_rule(root, 'never', {'artist': 'The Cure'}, 21))
            self.assertTrue(intake.add_rule(root, 'always', {'venue_id': 'v_x'}, 22))
            self.assertEqual(json.load(open(intake.prefs_file(root), encoding='utf-8')),
                             {'never': [{'artist': 'The Cure', 'issue': 21}],
                              'always': [{'venue_id': 'v_x', 'issue': 22}]})

    def test_a_corrected_prefs_issue_replaces_its_own_rule(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            write.write_json(intake.prefs_file(root), {'never': [], 'always': []})
            intake.poll(root, client=Fake([issue(21, PREFS)]), today=TODAY)
            corrected = PREFS.replace('בית ציוני אמריקה (מאירהוף)', 'היכל התרבות תל אביב - אולם צוקר')
            self.assertEqual(intake.poll(root, client=Fake([issue(21, corrected)]),
                                        today=TODAY)['results'],
                             [{'number': 21, 'result': 'prefs', 'problems': []}])
            self.assertEqual(json.load(open(intake.prefs_file(root), encoding='utf-8'))['never'],
                             [{'venue_id': 'v_8cd702b07b', 'issue': 21}])

    def test_closing_a_prefs_issue_retracts_its_rule(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            write.write_json(intake.prefs_file(root), {'never': [], 'always': []})
            intake.poll(root, client=Fake([issue(21, PREFS)]), today=TODAY)
            out = intake.poll(root, client=Fake([], states={21: 'closed'}), today=TODAY)
            self.assertEqual((out['retracted'], out['results']), (1, []))
            self.assertEqual(json.load(open(intake.prefs_file(root), encoding='utf-8')),
                             {'never': [], 'always': []})

    def test_the_prefs_issue_writes_the_file_and_receipts_the_rule(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            write.write_json(intake.prefs_file(root), {'never': [], 'always': []})
            client = Fake([issue(21, PREFS)])
            self.assertEqual(intake.poll(root, client=client, today=TODAY)['results'],
                             [{'number': 21, 'result': 'prefs', 'problems': []}])
            self.assertEqual(json.load(open(intake.prefs_file(root), encoding='utf-8'))['never'],
                             [{'venue_id': 'v_zionist_america_tlv', 'issue': 21}])
            self.assertIn('"venue_id": "v_zionist_america_tlv"', client.said[0][1])
            self.assertEqual(client.labels, [(21, 'processed')])

    def test_a_corrupt_prefs_file_fails_only_its_issue_and_the_poll_continues(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            write.write_bytes(intake.prefs_file(root), b'{')
            client = Fake([issue(20, PREFS), issue(21, EVENT)])
            results = intake.poll(root, client=client, today=TODAY)['results']
            self.assertEqual([r['result'] for r in results], ['failed', 'ingested'])
            self.assertIn('prefs.json', client.said[0][1])
            self.assertEqual(client.labels, [(21, 'processed')])

    def test_a_corrected_prefs_resubmission_clears_needs_info(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            write.write_json(intake.prefs_file(root), {'never': [], 'always': []})
            client = Fake([issue(21, PREFS, labels=('needs-info',))])
            self.assertEqual(intake.poll(root, client=client, today=TODAY)['results'],
                             [{'number': 21, 'result': 'prefs', 'problems': []}])
            self.assertEqual(client.labels, [(21, 'processed'), (21, '-needs-info')])

    def test_the_readme_documents_the_shape_the_writer_writes(self):
        text = open('README.md', encoding='utf-8').read()
        for token in ('"never"', '"always"', '"venue_id"', '"artist"', 'prefs.yml',
                      'gh label create', 'processed'):
            self.assertIn(token, text)


if __name__ == '__main__':
    unittest.main()
