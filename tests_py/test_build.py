import json, os, shutil, tempfile, unittest
from tools.getup import archive, build, human, venues, write

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

def served(root):
    return {ev['id']: ev for day in write.data_files(f'{root}/data')
            for ev in json.load(open(write.date_file(root, day), encoding='utf-8'))}

def rows(root):
    """Every committed row, duplicates included: a dict keyed by id can never show a second one."""
    return [ev for day in write.data_files(f'{root}/data')
            for ev in json.load(open(write.date_file(root, day), encoding='utf-8'))]

def human_draft(root, base, **overrides):
    venue = venues.load(root)[base['venue_id']]['name']
    draft = {'class': 'human', 'source': 'github', 'title': base['title'],
             'venue': venue, 'city': base['city'], 'start': base['start'],
             'url': 'https://github.com/roy/getup/issues/7',
             'tickets': None, 'community': None,
             'price_from': base['price_from'], 'desc': ''}
    return {**draft, **overrides}

class HumanPrecedenceTest(unittest.TestCase):
    def test_a_human_correction_survives_the_next_scan_and_is_not_duplicated(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            args = dict(sources=('leaan',), from_dir=CAPTURE, fetch=no_network, now=NOW)
            build.run(root, TODAY, **args)
            base = next(ev for ev in served(root).values() if ev['day'] == '2026-10-22')
            correction = human_draft(root, base, title='תיקון אנושי', price_from=7)
            write.write_json(human.store_file(root), {'7': correction})
            build.run(root, TODAY, **args)
            found = [ev for ev in rows(root) if ev['id'] == base['id']]
            self.assertEqual(len(found), 1)
            self.assertEqual((found[0]['title'], found[0]['price_from']), ('תיקון אנושי', 7))
            self.assertEqual(found[0]['source'], {'class': 'human', 'name': 'github'})
            self.assertEqual(found[0]['urls']['source'], 'https://github.com/roy/getup/issues/7')
            self.assertTrue(any(n.startswith(base['source']['name'])
                                for n in found[0]['enrichment']))
            build.run(root, TODAY, **args)
            self.assertEqual(len([ev for ev in rows(root) if ev['id'] == base['id']]), 1)

    def test_a_human_draft_gets_coordinates_when_its_new_venue_is_seeded(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            write.write_json(human.store_file(root), {'7': {
                'class': 'human', 'source': 'github', 'title': 'ערב ג׳אז במועדון החדש',
                'venue': 'מועדון חדש לגמרי', 'city': 'חיפה', 'start': 1794686400,
                'url': 'https://github.com/roy/getup/issues/7',
                'tickets': None, 'community': None, 'price_from': None, 'desc': ''}})
            build.run(root, TODAY, sources=('leaan',), from_dir=CAPTURE,
                      fetch=no_network, now=NOW)
            row = next(ev for ev in served(root).values()
                       if ev['title'] == 'ערב ג׳אז במועדון החדש')
            self.assertIsNotNone(row['lat'])          # provisioned, then geo.seed filled it
            self.assertIsNotNone(row['drive_min'])

    def test_a_human_row_never_stamps_seen_last(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            draft = {'class': 'human', 'source': 'github', 'title': 'ערב ג׳אז',
                     'venue': 'מועדון ללא סריקה', 'city': 'חיפה',
                     'start': 1794686400, 'url': 'https://github.com/roy/getup/issues/7',
                     'tickets': None, 'community': None, 'price_from': None, 'desc': ''}
            write.write_json(human.store_file(root), {'7': draft})
            build.run(root, TODAY, sources=('leaan',), from_dir=CAPTURE,
                      fetch=no_network, now=NOW)
            venue = next(v for v in venues.load(root).values()
                         if v.get('name') == 'מועדון ללא סריקה')
            self.assertNotEqual(venue.get('seen_last'), TODAY)

    def test_two_issues_for_one_event_are_one_row(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            args = dict(sources=('leaan',), from_dir=CAPTURE, fetch=no_network, now=NOW)
            build.run(root, TODAY, **args)
            base = next(ev for ev in served(root).values() if ev['day'] == '2026-10-22')
            draft = human_draft(root, base)
            write.write_json(human.store_file(root), {'7': draft, '8': dict(draft)})
            build.run(root, TODAY, **args)
            self.assertEqual(len([ev for ev in rows(root) if ev['id'] == base['id']]), 1)

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
        # the committed data dir also holds days past this fixture's horizon; those are stale too
        self.assertIn('2026-11-30', out['pruned'])
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
        write.write_json(write.date_file(self.root, '2026-11-30'), [{'id': 'stale'}])
        before = snapshot(self.root)
        out = build.run(self.root, TODAY, sources=('popit',), from_dir=f'{self.root}/empty',
                        fetch=no_network, now=NOW)
        self.assertEqual(out['counts']['popit'], 0)
        self.assertEqual(out['sources']['popit']['status'], 'failed')
        self.assertEqual(len([f for f in out['sources']['popit']['failures']
                              if f.startswith('popit:')]), 1)
        self.assertIsNone(out['pruned'])                           # the prune never ran
        self.assertEqual(snapshot(self.root), before)              # nothing blanked, nothing deleted

    def test_a_source_fully_absorbed_by_dedup_still_counts_from_its_survivors(self):
        from unittest import mock
        drafts = [{'title': 'הופעה', 'start': 1792954800, 'venue': 'בית נגלר קריית חיים',
                   'city': 'חיפה', 'source': name, 'class': cls}
                  for name, cls in (('leaan', 'aggregator'), ('popit', 'ticketing'))]
        with mock.patch.object(build.scan, 'scan_from_dir',
                               return_value=(drafts, {'leaan': 1, 'popit': 1}, [],
                                             {'leaan': 'ok', 'popit': 'ok'})):
            out = build.run(self.root, TODAY, sources=('leaan', 'popit'), from_dir=CAPTURE,
                            fetch=no_network, now=NOW)
        self.assertEqual(out['counts'], {'leaan': 1, 'popit': 1})  # counted before the merge
        self.assertEqual({s['status'] for s in out['sources'].values()}, {'ok'})

    def test_a_venue_scanned_with_no_event_in_the_window_is_still_seen(self):
        from unittest import mock
        draft = {'title': 'הופעה', 'start': 1796151600, 'venue': 'היכל התרבות ראשון לציון',
                 'city': 'ראשון לציון', 'source': 'leaan', 'class': 'aggregator'}
        with mock.patch.object(build.scan, 'scan_from_dir',
                               return_value=([draft], {'leaan': 1}, [], {'leaan': 'ok'})):
            out = build.run(self.root, TODAY, sources=('leaan',), from_dir=CAPTURE,
                            fetch=no_network, now=NOW)
        with open(f'{self.root}/venue/venues.json', encoding='utf-8') as f:
            reg = json.load(f)
        self.assertEqual(reg['v_heichal_tarbut_rishon']['seen_last'], TODAY)
        self.assertEqual(out['coverage']['missed'], [])            # the hall was read this morning
        self.assertTrue(all(not json.loads(body) for body in snapshot(self.root).values()))

    def test_a_scan_row_absorbed_by_a_human_row_still_stamps_seen_last(self):
        from unittest import mock
        draft = {'title': 'הופעה', 'start': 1796151600, 'venue': 'היכל התרבות ראשון לציון',
                 'city': 'ראשון לציון', 'source': 'leaan', 'class': 'aggregator'}
        with mock.patch.object(build.scan, 'scan_from_dir',
                               return_value=([draft], {'leaan': 1}, [], {'leaan': 'ok'})):
            build.run(self.root, TODAY, sources=('leaan',), from_dir=CAPTURE,
                      fetch=no_network, now=NOW)
            base = {'venue_id': 'v_heichal_tarbut_rishon', 'title': 'הופעה', 'city': 'ראשון לציון',
                    'start': 1796151600, 'price_from': None}
            write.write_json(human.store_file(self.root),
                             {'7': human_draft(self.root, base, title='תיקון אנושי')})
            out = build.run(self.root, TODAY, sources=('leaan',), from_dir=CAPTURE,
                            fetch=no_network, now=NOW)
        venue = venues.load(self.root)['v_heichal_tarbut_rishon']
        self.assertEqual(venue['seen_last'], TODAY)     # the only scan row was absorbed, not forgotten
        self.assertEqual(out['coverage']['missed'], [])

    def test_history_warns_on_a_corrupt_day_and_keeps_reading_the_rest(self):
        write.write_bytes(write.date_file(self.root, '2026-10-22'), b'{nope')
        write.write_json(write.date_file(self.root, '2026-10-23'),
                         [{'id': 'a', 'seen': {'first': '2026-10-01', 'last': '2026-10-02'}}])
        with self.assertLogs('getup', level='WARNING') as logs:
            seen = build.history(self.root)['seen']
        self.assertIn('2026-10-22', ' '.join(logs.output))
        self.assertEqual(seen['a'], {'first': '2026-10-01', 'last': '2026-10-02'})
