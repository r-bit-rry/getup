import unittest

from tools.getup import dedup


def rec(**o):
    base = {'id': 'a', 'venue_id': 'v', 'start': 1792780200, 'end': 1792787400, 'title': 't',
            'price_from': 100, 'soldout': False, 'source': {'class': 'ticketing', 'name': 'leaan'},
            'urls': {'tickets': 'https://t', 'community': None, 'source': 'https://s'},
            'notes': [], 'desc': 'd', 'enrichment': []}
    return {**base, **o}


class MergeTest(unittest.TestCase):
    def test_the_seller_owns_the_row_and_the_aggregator_becomes_enrichment(self):
        seller = rec(id='t1', price_from=174, soldout=True)
        aggr = rec(id='a1', start=1792780200 + 1200, price_from=120,
                   source={'class': 'aggregator', 'name': 'biluim'}, desc='חניה חופשית')
        out = dedup.merge([aggr, seller])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['id'], 't1')
        self.assertEqual(out[0]['price_from'], 174)          # seller wins on price
        self.assertTrue(out[0]['soldout'])
        self.assertEqual(out[0]['enrichment'], ['biluim: חניה חופשית'])

    def test_thirty_minutes_merges_and_thirty_one_does_not(self):
        self.assertEqual(len(dedup.merge([rec(id='a'), rec(id='b', start=1792780200 + 1800)])), 1)
        self.assertEqual(len(dedup.merge([rec(id='a'), rec(id='b', start=1792780200 + 1801)])), 2)

    def test_overlapping_windows_at_one_venue_stay_two_rows(self):
        club = rec(id='club', start=1792780200, end=1792780200 + 6 * 3600)
        dj = rec(id='dj', start=1792780200 + 3600, end=1792780200 + 2 * 3600)
        self.assertEqual(len(dedup.merge([club, dj])), 2)

    def test_a_lone_aggregator_keeps_its_source_class(self):
        [out] = dedup.merge([rec(id='a1', source={'class': 'aggregator', 'name': 'biluim'})])
        self.assertEqual(out['source']['class'], 'aggregator')

    def test_the_window_follows_the_first_start_and_nothing_joins_from_further_out(self):
        base = 1792780200
        rows = [rec(id='a', start=base), rec(id='b', start=base + 1500),
                rec(id='c', start=base + 3000)]
        self.assertEqual(len(dedup.merge(rows)), 2)

    def test_a_middle_record_cannot_pull_a_far_one_into_the_event(self):
        base = 1792780200
        rows = [rec(id='x', start=base), rec(id='y', start=base + 3000),
                rec(id='m', start=base + 1500)]
        self.assertEqual(len(dedup.merge(rows)), 2)
        self.assertEqual(len(dedup.merge(list(reversed(rows)))), 2)

    def test_six_ticketing_rows_every_thirty_minutes_are_not_one_event(self):
        base = 1792780200
        rows = [rec(id=f'r{i}', start=base + 1800 * i) for i in range(6)]
        self.assertEqual(len(dedup.merge(rows)), 3)

    def test_two_venues_at_the_same_hour_are_two_events(self):
        self.assertEqual(len(dedup.merge([rec(id='a'), rec(id='b', venue_id='v2')])), 2)

    def test_equal_rank_is_broken_by_the_normalized_title_then_the_id(self):
        a = rec(id='b', title='ערב-ג׳אז', source={'class': 'nightlife', 'name': 'popit'})
        b = rec(id='a', title='ערב ג׳אז', source={'class': 'nightlife', 'name': 'popit'})
        self.assertEqual(dedup.merge([a, b])[0]['id'], 'a')
        self.assertEqual(dedup.merge([b, a])[0]['id'], 'a')


class HumanTest(unittest.TestCase):
    def test_a_human_correction_beats_the_seller_and_keeps_its_fields(self):
        human_rec = rec(id='h1', title='ערב ג׳אז — תיקון', price_from=1,
                        source={'class': 'human', 'name': 'github'},
                        urls={'tickets': 'https://t', 'community': None,
                              'source': 'https://github.com/roy/getup/issues/7'})
        seller = rec(id='t1', price_from=174, soldout=True)
        out = dedup.merge([seller, human_rec])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['id'], 'h1')
        self.assertEqual(out[0]['title'], 'ערב ג׳אז — תיקון')
        self.assertEqual(out[0]['price_from'], 1)
        self.assertEqual(out[0]['source'], {'class': 'human', 'name': 'github'})
        self.assertEqual(out[0]['urls']['source'], 'https://github.com/roy/getup/issues/7')
        self.assertEqual(out[0]['enrichment'], ['leaan: d'])
        self.assertEqual(dedup.merge([human_rec, seller]), out)   # order cannot change the winner

    def test_a_human_record_is_never_absorbed_into_a_machine_row(self):
        human_rec = rec(id='h1', source={'class': 'human', 'name': 'github'})
        out = dedup.merge([rec(id='a1', start=1792780200 + 1200,
                               source={'class': 'aggregator', 'name': 'biluim'}), human_rec])
        self.assertEqual([r['source']['class'] for r in out], ['human'])
        self.assertEqual(out[0]['id'], 'h1')

    def test_thirty_one_minutes_away_is_still_a_second_event(self):
        human_rec = rec(id='h1', source={'class': 'human', 'name': 'github'})
        self.assertEqual(len(dedup.merge([human_rec, rec(id='t2', start=1792780200 + 1861)])), 2)


class SameSourceTest(unittest.TestCase):
    def test_two_rows_from_one_source_do_not_enrich_each_other(self):
        first = rec(id='a', start=1792780200, desc='הראשון')
        second = rec(id='b', start=1792780200 + 600, desc='השני')
        out = dedup.merge([first, second])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['enrichment'], [])

    def test_a_free_event_merges_on_the_same_rule(self):
        free = rec(id='a', price_from=0, source={'class': 'nightlife', 'name': 'popit'})
        other = rec(id='b', price_from=0, start=1792780200 + 900,
                    source={'class': 'aggregator', 'name': 'biluim'})
        self.assertEqual(len(dedup.merge([free, other])), 1)

    def test_the_loser_donates_what_the_winner_lacks_and_never_overwrites(self):
        seller = rec(id='t1', notes=['מומלץ'], urls={'tickets': 'https://t', 'community': None,
                                                      'source': 'https://s'})
        aggr = rec(id='a1', source={'class': 'aggregator', 'name': 'biluim'},
                   urls={'tickets': None, 'community': 'https://c', 'source': 'https://a'},
                   notes=['מומלץ', 'חניה'])
        [out] = dedup.merge([seller, aggr])
        self.assertEqual(out['urls']['tickets'], 'https://t')
        self.assertEqual(out['urls']['community'], 'https://c')
        self.assertEqual(out['notes'], ['מומלץ', 'חניה'])

    def test_the_input_is_not_mutated(self):
        aggr = rec(id='a1', source={'class': 'aggregator', 'name': 'biluim'})
        seller = rec(id='t1')
        dedup.merge([aggr, seller])
        self.assertEqual(aggr['enrichment'], [])
        self.assertEqual(seller['enrichment'], [])

    def test_input_order_cannot_change_the_output(self):
        rows = [rec(id='c', start=1792780200 + 60),
                rec(id='a', start=1792780200 + 1500),
                rec(id='b', start=1792780200 + 900)]
        self.assertEqual([r['id'] for r in dedup.merge(rows)],
                         [r['id'] for r in dedup.merge(list(reversed(rows)))])

    def test_two_rows_with_one_start_and_one_id_pick_a_winner_the_same_way_every_time(self):
        a = rec(id='a', source={'class': 'aggregator', 'name': 'biluim'}, desc='x')
        b = rec(id='a', source={'class': 'aggregator', 'name': 'other'}, desc='y')
        self.assertEqual(dedup.merge([a, b]), dedup.merge([b, a]))

    def test_a_duplicate_that_differs_only_in_price_picks_the_same_winner_either_way(self):
        a = rec(id='a', price_from=174)
        b = rec(id='a', price_from=99)
        self.assertEqual(len(dedup.merge([a, b])), 1)
        self.assertEqual(dedup.merge([a, b]), dedup.merge([b, a]))

    def test_the_seller_wins_whoever_arrives_first(self):
        seller = rec(id='t1', price_from=174)
        aggr = rec(id='a1', start=1792780200 + 1200, price_from=120,
                   source={'class': 'aggregator', 'name': 'biluim'}, desc='חניה חופשית')
        forward, backward = dedup.merge([aggr, seller]), dedup.merge([seller, aggr])
        self.assertEqual(forward, backward)
        self.assertEqual([r['id'] for r in forward], ['t1'])

    def test_a_minimal_record_does_not_crash_the_fold(self):
        bare = [{'id': 'x', 'venue_id': 'v', 'start': 1},
                {'id': 'y', 'venue_id': 'v', 'start': 2}]
        out = dedup.merge(bare)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['id'], 'x')
        self.assertEqual(out[0]['enrichment'], [])

    def test_enrichment_notes_are_capped(self):
        aggr = rec(id='a1', source={'class': 'aggregator', 'name': 'biluim'}, desc='x' * 500)
        self.assertEqual(len(dedup.enrichment_note(aggr)), 200)
        self.assertTrue(dedup.enrichment_note(aggr).startswith('biluim: '))

    def test_a_loser_with_nothing_to_say_adds_no_empty_note(self):
        bare = rec(id='a1', desc='', source={'class': 'aggregator', 'name': 'biluim'},
                   urls={'tickets': None, 'community': None, 'source': None})
        self.assertEqual(dedup.enrichment_note(bare), '')
        [out] = dedup.merge([rec(id='t1'), bare])
        self.assertEqual(out['enrichment'], [])
