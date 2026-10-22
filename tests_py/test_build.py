import json, os, shutil, tempfile, unittest
from tools.getup import archive, build, write

CAPTURE = 'docs/research/2026-10-21'
TODAY = '2026-10-21'
NOW = '2026-10-21T04:15:00Z'

def fresh(root):
    shutil.copytree('venue', f'{root}/venue')
    shutil.copytree('data', f'{root}/data')

def blob(path):
    with open(path, 'rb') as f:
        return f.read()

def snapshot(root):
    return {day: blob(write.date_file(root, day))
            for day in write.data_files(f'{root}/data')}

def no_network(url, **kw):
    raise AssertionError(f'network call in cassette mode: {url}')

class BuildTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        fresh(self.root)

    def test_two_runs_on_unchanged_cassettes_are_byte_identical(self):
        build.run(self.root, TODAY, sources=('leaan', 'popit'), from_dir=CAPTURE,
                  fetch=no_network, now=NOW)
        first = snapshot(self.root)
        first_venues = blob(f'{self.root}/venue/venues.json')
        first_index = blob(write.index_file(self.root))
        build.run(self.root, TODAY, sources=('leaan', 'popit'), from_dir=CAPTURE,
                  fetch=no_network, now=NOW)
        self.assertEqual(snapshot(self.root), first)
        self.assertEqual(blob(f'{self.root}/venue/venues.json'), first_venues)
        self.assertEqual(blob(write.index_file(self.root)), first_index)

    def test_the_index_counts_match_the_files_it_lists(self):
        out = build.run(self.root, TODAY, sources=('leaan',), from_dir=CAPTURE,
                        fetch=no_network, now=NOW)
        with open(write.index_file(self.root), encoding='utf-8') as f:
            idx = json.load(f)
        self.assertEqual({d['date'] for d in idx['dates']}, set(snapshot(self.root)))
        for d in idx['dates']:
            self.assertEqual(len(json.loads(snapshot(self.root)[d['date']])), d['count'])
        self.assertEqual(idx['sources']['leaan']['status'], 'ok')
        self.assertEqual(out['counts']['leaan'], idx['sources']['leaan']['count'])

    def test_nothing_outside_the_thirty_day_horizon_is_stored(self):
        build.run(self.root, TODAY, sources=('leaan',), from_dir=CAPTURE, fetch=no_network, now=NOW)
        days = write.data_files(f'{self.root}/data')
        self.assertEqual((days[0], days[-1]), ('2026-10-21', '2026-11-19'))
        self.assertEqual(len(days), build.SERVE_DAYS)   # every horizon day exists, empty ones included

    def test_seen_first_survives_the_next_run(self):
        build.run(self.root, TODAY, sources=('leaan',), from_dir=CAPTURE, fetch=no_network, now=NOW)
        first_event = json.loads(snapshot(self.root)['2026-10-22'])[0]
        self.assertEqual(first_event['seen']['first'], TODAY)
        self.assertEqual(build.history(self.root)['seen'][first_event['id']]['first'], TODAY)
        build.run(self.root, '2026-10-22', sources=('leaan',), from_dir=CAPTURE,
                  fetch=no_network, now='2026-10-22T04:15:00Z')
        again = {ev['id']: ev for ev in json.loads(snapshot(self.root)['2026-10-22'])}
        self.assertEqual(again[first_event['id']]['seen'], {'first': TODAY, 'last': '2026-10-22'})

    def test_history_reads_an_archived_month_so_first_survives_the_roll(self):
        path = archive.month_file(self.root, '2026-07')
        payload = {'2026-07-01': [{'id': 'old', 'seen': {'first': '2026-06-30',
                                                         'last': '2026-07-01'}}]}
        write.write_bytes(path, archive.compress(write.dumps(payload).encode('utf-8'),
                                                 os.path.splitext(path)[1]))
        self.assertEqual(build.history(self.root)['seen']['old'],
                         {'first': '2026-06-30', 'last': '2026-07-01'})

    def test_the_build_never_writes_the_label_cache(self):
        before = blob(f'{self.root}/data/labels.json')
        build.run(self.root, TODAY, sources=('leaan',), from_dir=CAPTURE, fetch=no_network, now=NOW)
        self.assertEqual(blob(f'{self.root}/data/labels.json'), before)

    def test_a_source_that_returns_nothing_is_reported_and_deletes_nothing(self):
        os.makedirs(f'{self.root}/empty')
        with open(f'{self.root}/empty/popit.xml', 'w') as f:
            f.write('<rss><channel></channel></rss>')
        write.write_json(write.date_file(self.root, '2026-11-30'), [{'id': 'stale'}])
        before = snapshot(self.root)
        out = build.run(self.root, TODAY, sources=('popit',), from_dir=f'{self.root}/empty',
                        fetch=no_network, now=NOW)
        self.assertEqual(out['sources']['popit']['status'], 'failed')
        self.assertIsNone(out['pruned'])
        self.assertEqual(snapshot(self.root), before)              # nothing written, nothing deleted
        with open(write.index_file(self.root), encoding='utf-8') as f:
            idx = json.load(f)
        self.assertEqual(idx['sources']['popit']['status'], 'failed')
        self.assertEqual({d['date'] for d in idx['dates']}, set(snapshot(self.root)))  # still listed

    def test_a_fully_ok_run_prunes_a_stale_future_day(self):
        write.write_json(write.date_file(self.root, '2026-11-30'), [{'id': 'stale'}])
        out = build.run(self.root, TODAY, sources=('leaan',), from_dir=CAPTURE, fetch=no_network, now=NOW)
        self.assertEqual(out['pruned'], ['2026-11-30'])
        self.assertNotIn('2026-11-30', snapshot(self.root))

    def test_a_partial_source_writes_its_records_but_never_prunes(self):
        from unittest import mock
        from tools.getup import scan
        drafts, counts, _, _ = scan.scan_from_dir(['leaan'], CAPTURE)
        write.write_json(write.date_file(self.root, '2026-11-30'), [{'id': 'stale'}])
        with mock.patch.object(build.scan, 'scan_from_dir',
                               return_value=(drafts, counts, ['leaan: https://x: 503'],
                                             {'leaan': 'partial'})):
            out = build.run(self.root, TODAY, sources=('leaan',), from_dir=CAPTURE,
                            fetch=no_network, now=NOW)
        self.assertIsNone(out['pruned'])
        self.assertEqual(out['sources']['leaan'],
                         {'status': 'partial', 'count': len(drafts),
                          'failures': ['leaan: https://x: 503']})
        self.assertTrue(snapshot(self.root)['2026-10-22'])         # the survivors were still written
        self.assertIn('2026-11-30', snapshot(self.root))           # the stale day was left alone

    def test_unpinned_and_venueless_events_are_counted_not_invented(self):
        out = build.run(self.root, TODAY, sources=('leaan', 'popit'), from_dir=CAPTURE,
                        fetch=no_network, now=NOW)
        with open(write.index_file(self.root), encoding='utf-8') as f:
            idx = json.load(f)
        self.assertGreater(idx['unpinned'], 0)                     # cities the capture does not geocode stay unpinned
        self.assertGreater(idx['dropped_no_venue'], 0)             # Popit's "מיקום לא ידוע" items
        self.assertEqual(idx['unpinned'], out['unpinned'])
        for body in snapshot(self.root).values():
            for ev in json.loads(body):
                if ev['lat'] is None:
                    self.assertIsNone(ev['lon'])
                    self.assertIsNone(ev['drive_min'])

    def test_every_served_venue_from_the_capture_has_finite_drive_minutes(self):
        build.run(self.root, TODAY, sources=('leaan', 'popit'), from_dir=CAPTURE,
                  fetch=no_network, now=NOW)
        with open(f'{self.root}/venue/venues.json', encoding='utf-8') as f:
            reg = json.load(f)
        with open(f'{CAPTURE}/geo-drive.json', encoding='utf-8') as f:
            known = json.load(f)['drive']
        served = [ev for body in snapshot(self.root).values() for ev in json.loads(body)]
        placed = [ev for ev in served if reg[ev['venue_id']]['city'] in known]
        self.assertTrue(placed)                                    # the capture covers most of the served set
        for ev in placed:
            self.assertIsInstance(ev['drive_min'], int)             # a placed city never yields null minutes

    def test_every_written_event_satisfies_the_client_contract(self):
        build.run(self.root, TODAY, sources=('leaan', 'popit'), from_dir=CAPTURE,
                  fetch=no_network, now=NOW)
        with open(f'{self.root}/venue/venues.json', encoding='utf-8') as f:
            reg = json.load(f)
        for path, body in snapshot(self.root).items():
            for ev in json.loads(body):
                self.assertIn(ev['venue_id'], reg, path)
                self.assertNotIn('daypart', ev)
                self.assertNotIn('tags', ev)
                self.assertLessEqual(len(ev['desc']), 601)
                self.assertIn(ev['format'], ['live_band', 'tribute', 'dj_set', 'orchestra',
                                             'standup', 'theatre', 'festival', 'unknown'])
                self.assertIsInstance(ev['notes'], list)
                self.assertTrue(all(isinstance(n, str) for n in ev['notes']))

    def test_a_source_whose_every_draft_lacks_a_clock_is_failed_with_zero(self):
        # Popit parses the item, normalize drops it for having no start: the tally must not say ok
        os.makedirs(f'{self.root}/empty', exist_ok=True)
        with open(f'{self.root}/empty/popit.xml', 'w') as f:
            f.write('<rss><channel><item><title>מסיבה — נמל תל אביב</title>'
                    '<description>מסיבה, נמל תל אביב</description></item></channel></rss>')
        out = build.run(self.root, TODAY, sources=('popit',), from_dir=f'{self.root}/empty',
                        fetch=no_network, now=NOW)
        self.assertEqual(out['counts']['popit'], 0)
        self.assertEqual(out['sources']['popit']['status'], 'failed')
        self.assertEqual(len([f for f in out['sources']['popit']['failures']
                              if f.startswith('popit:')]), 1)
