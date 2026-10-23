import os
import tempfile
import unittest
from tools.getup import archive, coverage, write

REG = {'v_major': {'id': 'v_major', 'name': 'היכל גדול', 'tier': 'major'},
       'v_quiet': {'id': 'v_quiet', 'name': 'אולם שקט', 'tier': 'major'},
       'v_room': {'id': 'v_room', 'name': 'מועדון', 'tier': 'room'}}

def rec(venue_id, day, last):
    return {'venue_id': venue_id, 'day': day, 'seen': {'first': last, 'last': last}}

def archive_report(last):
    """A root whose only sighting of v_major is inside one archived member."""
    with tempfile.TemporaryDirectory() as root:
        write.write_json(f'{root}/venue/venues.json', REG)
        path = archive.month_file(root, '2026-09')
        payload = {'2026-09-20': [rec('v_major', '2026-09-20', last)]}
        write.write_bytes(path, archive.compress(write.dumps(payload).encode('utf-8'),
                                                 os.path.splitext(path)[1]))
        return coverage.report(root, '2026-10-21')

class CoverageTest(unittest.TestCase):
    def test_a_major_venue_with_no_recent_sighting_is_missed(self):
        recs = [rec('v_major', '2026-10-21', '2026-10-20'), rec('v_room', '2026-10-21', '2026-10-21')]
        out = coverage.check(REG, recs, '2026-10-21')
        self.assertEqual(out['checked'], 2)                       # only major venues are checked
        self.assertEqual(out['missed'], [{'venue_id': 'v_quiet', 'name': 'אולם שקט'}])

    def test_a_future_event_with_a_stale_last_seen_is_still_missed(self):
        # the event is on sale for November, but nothing has been seen here for twenty days
        seen_today = rec('v_major', '2026-10-21', '2026-10-21')
        stale = [seen_today, rec('v_quiet', '2026-11-10', '2026-10-01')]
        missed = [m['venue_id'] for m in coverage.check(REG, stale, '2026-10-21')['missed']]
        self.assertEqual(missed, ['v_quiet'])

    def test_a_fresh_sighting_keeps_a_venue_alive_when_every_event_is_far_out(self):
        # seen three days ago, and its only events are twenty days away: the date window must not hide it
        fresh = [rec('v_major', '2026-10-21', '2026-10-21'), rec('v_quiet', '2026-11-10', '2026-10-18')]
        self.assertEqual(coverage.check(REG, fresh, '2026-10-21')['missed'], [])

    def test_the_window_is_fourteen_days_ending_today(self):
        seen_today = rec('v_major', '2026-10-21', '2026-10-21')
        inside = [seen_today, rec('v_quiet', '2026-10-08', '2026-10-08')]    # 13 days back
        self.assertEqual(coverage.check(REG, inside, '2026-10-21')['missed'], [])
        outside = [seen_today, rec('v_quiet', '2026-10-06', '2026-10-06')]   # 15 days back
        self.assertEqual([m['venue_id'] for m in coverage.check(REG, outside, '2026-10-21')['missed']],
                         ['v_quiet'])

    def test_the_fixture_registry_checks_three_major_venues(self):
        # the committed fixtures carry seen.last == 2026-10-21, so every major venue is seen today
        out = coverage.report('.', '2026-10-21')
        self.assertEqual(out['checked'], 3)
        self.assertEqual(out['missed'], [])

    def test_last_seen_by_venue_takes_the_maximum_and_ignores_the_rest(self):
        recs = [rec('v_major', '2026-10-21', '2026-10-19'),
                rec('v_major', '2026-11-01', '2026-10-20'),
                {'venue_id': 'v_major'}, {'venue_id': 'v_room', 'seen': {}}]
        self.assertEqual(coverage.last_seen_by_venue(recs),
                         {'v_major': '2026-10-20'})

    def test_a_recent_sighting_inside_an_archive_member_is_not_missed(self):
        missed = {m['venue_id'] for m in archive_report('2026-10-20')['missed']}
        self.assertNotIn('v_major', missed)
        self.assertIn('v_quiet', missed)

    def test_an_old_sighting_inside_an_archive_member_is_missed(self):
        missed = {m['venue_id'] for m in archive_report('2026-09-01')['missed']}
        self.assertIn('v_major', missed)

    def test_the_registry_scan_date_wins_and_the_file_scan_is_only_the_fallback(self):
        seen_today = dict(REG['v_major'], seen_last='2026-10-21')
        self.assertEqual(coverage.check({'v_major': seen_today}, [], '2026-10-21')['missed'], [])
        stale = dict(REG['v_major'], seen_last='2026-09-01')       # the registry is the truth
        self.assertEqual([m['venue_id'] for m in coverage.check(
            {'v_major': stale}, [rec('v_major', '2026-10-21', '2026-10-21')], '2026-10-21')['missed']],
            ['v_major'])
