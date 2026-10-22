import json, os, unittest
from tools.getup import scan
from tools.getup.adapters import leaan

CAPTURE = 'docs/research/2026-10-21/leaan-events.json'

def events():
    return json.load(open(CAPTURE, encoding='utf-8'))

class ShapeTest(unittest.TestCase):
    def test_the_capture_is_a_bare_event_list(self):
        drafts = leaan.parse(events())
        self.assertEqual(len(drafts), 215)

    def test_the_raw_next_data_dict_is_accepted(self):
        payload = {'props': {'pageProps': {'initialState': {'pageData': {'events': events()}}}}}
        self.assertEqual(len(leaan.parse(payload)), 215)

    def test_an_html_page_is_read_through_the_script_tag(self):
        payload = ('<html><body><script id="__NEXT_DATA__" type="application/json">'
                   + json.dumps({'props': {'pageProps': {'initialState': {'pageData': {'events': events()}}}}}))
        payload += '</script></body></html>'
        self.assertEqual(len(leaan.parse(payload)), 215)

    def test_an_empty_event_list_is_a_quiet_zero(self):
        html = ('<html><body><script id="__NEXT_DATA__" type="application/json">'
                '{"props":{"pageProps":{"initialState":{"pageData":{"events":[]}}}}}'
                '</script></body></html>')
        with self.assertNoLogs('getup', level='WARNING'):
            self.assertEqual(leaan.parse(html), [])

    def test_a_changed_shape_warns_once_and_yields_no_events(self):
        with self.assertLogs('getup', level='WARNING') as logs:
            drafts = leaan.parse({'props': {'pageProps': {}}})
        self.assertEqual(drafts, [])
        self.assertEqual(len(logs.output), 1)
        self.assertIn('leaan', logs.output[0])
        self.assertIn('pageData.events', logs.output[0])

    def test_a_scalar_where_the_event_list_belongs_is_not_iterated_as_characters(self):
        payload = {'props': {'pageProps': {'initialState': {'pageData': {'events': 'nope'}}}}}
        with self.assertLogs('getup', level='WARNING'):
            self.assertEqual(leaan.parse(payload), [])

    def test_a_non_object_record_is_skipped_with_its_index(self):
        events_ = [{'event_id': 'a', 'title': 't', 'venue': 'v', 'city': 'c', 'start': 1792780200}, 7]
        payload = {'props': {'pageProps': {'initialState': {'pageData': {'events': events_}}}}}
        with self.assertLogs('getup', level='WARNING') as logs:
            drafts = leaan.parse(payload)
        self.assertEqual([d['source_id'] for d in drafts], ['a'])
        self.assertIn('leaan[1]', logs.output[0])

class DraftTest(unittest.TestCase):
    def test_the_real_capture_yields_215_ticket_seller_drafts(self):
        first = leaan.parse(events())[0]
        self.assertEqual((first['class'], first['source']), ('ticketing', 'leaan'))
        self.assertEqual(first['source_id'], '6a1be86c43116ffad6fea591')
        self.assertEqual(first['venue'], 'מרכז עזריאלי')
        self.assertEqual(first['city'], 'תל אביב')
        self.assertEqual(first['start'], 1780988400)
        self.assertEqual(first['tags'], ['הצגות והרצאות'])
        self.assertEqual(first['url'], 'https://www.leaan.co.il/event/6a1be86c43116ffad6fea591')

@unittest.skipUnless(os.environ.get('GETUP_LIVE'), 'live source; set GETUP_LIVE=1')
class LeaanLiveTest(unittest.TestCase):
    def test_the_category_pages_still_answer_with_events(self):
        drafts, counts, failures, status = scan.scan(['leaan'])
        self.assertEqual((failures, status), ([], {'leaan': 'ok'}))
        self.assertGreater(counts['leaan'], 0)
