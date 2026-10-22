import os, tempfile, unittest
from tools.getup import scan

class Stub:
    NAME = 'stub'; CLASS = 'aggregator'; CASSETTE = 'stub.html'
    URLS = ['https://a', 'https://b']
    @staticmethod
    def parse(payload):
        if payload == 'boom':
            raise ValueError('page shape changed')
        return [{'source': 'stub', 'class': 'aggregator', 'source_id': payload,
                 'title': 't', 'venue': 'v', 'city': 'c', 'start': 1792780200}] if payload == 'ok' else []

def stub_scan(fetch, names=('stub',)):
    return scan.scan(list(names), fetch=fetch, adapters={'stub': Stub})

class StatusTest(unittest.TestCase):
    def test_every_url_answering_is_ok(self):
        drafts, counts, failures, status = stub_scan(lambda url, **k: 'ok')
        self.assertEqual((len(drafts), counts, failures, status),
                         (2, {'stub': 2}, [], {'stub': 'ok'}))

    def test_one_dead_url_is_partial_and_the_other_urls_still_produce_drafts(self):
        def fetch(url, **kw):
            if url.endswith('/a'):
                raise scan.FetchError('503')
            return 'ok'
        drafts, counts, failures, status = stub_scan(fetch)
        self.assertEqual(len(drafts), 1)
        self.assertEqual(status, {'stub': 'partial'})
        self.assertEqual(len(failures), 1)
        self.assertIn('stub', failures[0])

    def test_every_url_dead_is_failed_and_nothing_raises(self):
        def fetch(url, **kw):
            raise scan.FetchError('offline')
        drafts, counts, failures, status = stub_scan(fetch)
        self.assertEqual((drafts, counts, status), ([], {'stub': 0}, {'stub': 'failed'}))

    def test_a_parser_that_raises_is_a_failed_source_not_a_crash(self):
        drafts, counts, failures, status = stub_scan(lambda url, **k: 'boom')
        self.assertEqual((drafts, status), ([], {'stub': 'failed'}))
        self.assertIn('page shape changed', failures[0])

    def test_zero_events_from_working_urls_is_failed(self):
        drafts, counts, failures, status = stub_scan(lambda url, **k: 'empty')
        self.assertEqual(status, {'stub': 'failed'})

    def test_an_unknown_source_name_is_an_argument_error(self):
        with self.assertRaises(ValueError):
            scan.scan(['nope'])

class CassetteTest(unittest.TestCase):
    def test_cassette_mode_reads_the_file_and_never_touches_the_network(self):
        with tempfile.TemporaryDirectory() as root:
            open(os.path.join(root, 'stub.html'), 'w').write('ok')
            def boom(url, **kw):
                raise AssertionError(f'network call in cassette mode: {url}')
            drafts, counts, failures, status = scan.scan_from_dir(['stub'], root, adapters={'stub': Stub})
            self.assertEqual((len(drafts), status), (1, {'stub': 'ok'}))
