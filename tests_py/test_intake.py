import html
import json
import os
import shutil
import tempfile
import unittest

from tools.getup import human, intake, venues, write
from tests_py.github_fake import Fake, issue
from tests_py.test_intake_parse import EVENT

TODAY = '2026-10-21'


def fresh(root):
    shutil.copytree('venue', f'{root}/venue')
    os.makedirs(f'{root}/data')
    write.write_json(human.store_file(root), {})


class GuardTest(unittest.TestCase):
    def test_a_non_member_issue_writes_nothing_at_all(self):
        for assoc in ('NONE', 'CONTRIBUTOR', 'COLLABORATOR', 'FIRST_TIME_CONTRIBUTOR'):
            with tempfile.TemporaryDirectory() as root:
                fresh(root)
                client = Fake([issue(7, EVENT, assoc)])
                self.assertEqual(intake.poll(root, client=client, today=TODAY),
                                 [{'number': 7, 'result': 'skipped', 'problems': []}])
                self.assertEqual((client.said, client.labels, human.load(root)), ([], [], {}))


class EventTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        fresh(self.root)
        self.client = Fake([issue(7, EVENT.replace('https://example.com/t/1', 'https://x/t'))])

    def test_a_valid_issue_stores_the_canonical_draft_with_a_receipt_and_processed(self):
        self.assertEqual(intake.poll(self.root, client=self.client, today=TODAY),
                         [{'number': 7, 'result': 'ingested', 'problems': []}])
        stored = human.load(self.root)['7']
        self.assertEqual((stored['venue'], stored['start']),
                         ('בית ציוני אמריקה (מאירהוף), תל אביב', 1794686400))
        self.assertEqual((stored['class'], stored['source']), ('human', 'github'))
        self.assertEqual((stored['url'], stored['tickets']),
                         ('https://example.com/e/1', 'https://x/t'))
        self.assertNotIn('venue_id', stored)        # placement belongs to the build
        self.assertNotIn('drive_min', stored)
        self.assertEqual(self.client.labels, [(7, 'processed')])
        body = self.client.said[0][1]
        self.assertTrue(body.startswith(intake.RECEIPT_MARK))
        self.assertIn('נקלט', body)
        self.assertIn(json.dumps(stored, ensure_ascii=False, indent=1, sort_keys=True),
                      html.unescape(body))

    def test_a_second_issue_for_an_ingested_event_receipts_a_merge_not_an_intake(self):
        client = Fake([issue(7, EVENT), issue(8, EVENT)])
        self.assertEqual([r['result'] for r in intake.poll(self.root, client=client, today=TODAY)],
                         ['ingested', 'merged'])
        self.assertIn('מוזג לאירוע קיים', client.said[1][1])
        self.assertNotIn('נקלט', client.said[1][1])

    def test_replaying_the_same_issue_posts_no_second_comment_and_stores_one_draft(self):
        intake.poll(self.root, client=self.client, today=TODAY)
        intake.poll(self.root, client=self.client, today=TODAY)
        self.assertEqual(len(human.load(self.root)), 1)
        self.assertEqual(len(self.client.said), 1)

    def test_a_correction_replaces_the_record_for_that_issue_number(self):
        intake.poll(self.root, client=self.client, today=TODAY)
        corrected = EVENT.replace('ערב ג׳אז', 'ערב ג׳אז — תיקון')
        client = Fake([issue(7, corrected)])
        self.assertEqual(intake.poll(self.root, client=client, today=TODAY),
                         [{'number': 7, 'result': 'ingested', 'problems': []}])
        self.assertEqual(len(human.load(self.root)), 1)
        self.assertEqual(human.load(self.root)['7']['title'], 'ערב ג׳אז — תיקון')

    def test_a_malformed_issue_names_the_field_and_changes_no_file(self):
        before = open(human.store_file(self.root), 'rb').read()
        client = Fake([issue(8, EVENT.replace('### שעה\n\n22:00', '### שעה\n\n_No response_'))])
        self.assertEqual(intake.poll(self.root, client=client, today=TODAY),
                         [{'number': 8, 'result': 'needs-info', 'problems': ['שעה']}])
        self.assertEqual(human.load(self.root), {})
        self.assertEqual(client.said, [(8, intake.info(['שעה']))])
        self.assertEqual(client.labels, [(8, 'needs-info')])
        self.assertEqual(open(human.store_file(self.root), 'rb').read(), before)

    def test_a_failed_comment_is_a_failed_issue_and_the_poll_continues(self):
        client = Fake([issue(7, EVENT), issue(8, EVENT.replace('2026-11-14', '2026-11-15'))])
        real = client.comment

        def broken(n, body):
            if n == 7:
                raise intake.GithubError(500, 'server error')
            real(n, body)

        client.comment = broken
        results = intake.poll(self.root, client=client, today=TODAY)
        self.assertEqual([r['result'] for r in results], ['failed', 'ingested'])

    def test_a_corrupt_state_file_fails_one_issue_with_a_named_comment_and_continues(self):
        write.write_json(human.store_file(self.root), ['not', 'an', 'object'])
        client = Fake([issue(7, EVENT), issue(8, EVENT)])
        results = intake.poll(self.root, client=client, today=TODAY)
        self.assertEqual([r['result'] for r in results], ['failed', 'failed'])
        self.assertIn('human.json', client.said[0][1])
        self.assertIn('human.json', client.said[1][1])
        self.assertEqual(client.labels, [])             # a failed issue changes no label

    def test_an_unrecognised_body_is_needs_info_not_a_guess(self):
        client = Fake([issue(9, '### מה זה\n\nמשהו אחר')])
        self.assertEqual(intake.poll(self.root, client=client, today=TODAY),
                         [{'number': 9, 'result': 'needs-info', 'problems': ['טופס לא מזוהה']}])


class SourceTest(unittest.TestCase):
    def test_a_source_request_is_receipted_and_processed_without_touching_records(self):
        from tests_py.test_intake_parse import SOURCE
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            client = Fake([issue(11, SOURCE)])
            self.assertEqual(intake.poll(root, client=client, today=TODAY),
                             [{'number': 11, 'result': 'source', 'problems': []}])
            self.assertIn('"kind": "aggregator"', html.unescape(client.said[0][1]))
            self.assertEqual((client.labels, human.load(root)), ([(11, 'processed')], {}))


if __name__ == '__main__':
    unittest.main()
