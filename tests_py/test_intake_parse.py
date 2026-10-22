import re
import unittest

from tools.getup import intake

EVENT = '''### שם האירוע

ערב ג׳אז

### שם המקום

בית ציוני אמריקה (מאירהוף), תל אביב

### עיר

תל אביב

### תאריך

2026-11-14

### שעה

22:00

### מחיר

_No response_

### קישור לאירוע

https://example.com/e/1

### קישור לכרטיסים

https://example.com/t/1

### קהילה סגורה (קישור לקבוצה)

- [ ] קהילה סגורה (קישור לקבוצה)

### תיאור

רביעיית ג׳אז
'''

GATED = EVENT.replace('- [ ]', '- [X]').replace(
    'https://example.com/e/1', 'https://facebook.com/groups/x').replace(
    'https://example.com/t/1', '_No response_')
SOURCE = '''### שם המקור

בילום

### כתובת המקור

https://biluim.co.il

### סוג המקור

אגרגטור

### מה חסר היום

חסרים אירועים מחוץ לתל אביב
'''


def form_items(path):
    """`id` -> (the heading GitHub renders, its option labels): the strings the parser keys on."""
    items = {}
    for block in re.split(r'^  - type: \w+\n', open(path, encoding='utf-8').read(), flags=re.M)[1:]:
        ident = re.search(r'^    id: (\S+)$', block, re.M).group(1)
        label = re.search(r'^      label: (.+)$', block, re.M)
        items[ident] = (label.group(1).strip() if label else None,
                        [text.strip() for text in re.findall(r'^        - label: (.+)$', block, re.M)])
    return items


class FormTest(unittest.TestCase):
    def test_headings_become_fields_and_no_response_is_empty(self):
        fields = intake.parse_form(EVENT)
        self.assertEqual(fields['שם האירוע'], 'ערב ג׳אז')
        self.assertEqual(fields['מחיר'], '')
        self.assertNotIn('קהילה סגורה (קישור לקבוצה)', fields)

    def test_a_checked_box_is_a_key(self):
        self.assertEqual(intake.parse_form(GATED)['קהילה סגורה (קישור לקבוצה)'], 'x')

    def test_every_form_field_id_is_one_the_parser_knows(self):
        # Only top-level `- type:` blocks carry ids; a dropdown option is `- label:` and is skipped.
        for path, known in (('.github/ISSUE_TEMPLATE/event.yml', intake.EVENT_IDS),
                            ('.github/ISSUE_TEMPLATE/source.yml', intake.SOURCE_IDS),
                            ('.github/ISSUE_TEMPLATE/prefs.yml', intake.PREFS_IDS)):
            ids = re.findall(r'^\s*- type: \w+\n\s+id: (\S+)',
                             open(path, encoding='utf-8').read(), re.M)
            self.assertEqual(len(ids), len(set(ids)), path)
            self.assertEqual(set(ids), set(known), path)

    def test_every_form_label_is_the_heading_the_parser_keys_on(self):
        for path, ids, labels in (
                ('.github/ISSUE_TEMPLATE/event.yml', intake.EVENT_IDS, intake.EVENT_FIELDS),
                ('.github/ISSUE_TEMPLATE/source.yml', intake.SOURCE_IDS, intake.SOURCE_FIELDS),
                ('.github/ISSUE_TEMPLATE/prefs.yml', intake.PREFS_IDS, intake.PREFS_FIELDS)):
            items = form_items(path)
            self.assertEqual([items[i][0] for i in ids], list(labels), path)

    def test_the_gated_checkbox_option_is_the_field_the_draft_reads(self):
        self.assertEqual(form_items('.github/ISSUE_TEMPLATE/event.yml')['event-gated'],
                         (intake.EVENT_FIELDS[8], [intake.EVENT_FIELDS[8]]))


class EventTest(unittest.TestCase):
    def test_a_complete_form_is_one_human_draft(self):
        draft, problems = intake.event_draft(intake.parse_form(EVENT), '2026-10-21')
        self.assertEqual(problems, [])
        self.assertEqual(draft['class'], 'human')
        self.assertEqual(draft['source'], 'github')
        self.assertEqual(draft['start'], 1794686400)          # 2026-11-14 22:00 IST
        self.assertEqual((draft['venue'], draft['city']),
                         ('בית ציוני אמריקה (מאירהוף), תל אביב', 'תל אביב'))
        self.assertEqual((draft['url'], draft['tickets'], draft['community']),
                         ('https://example.com/e/1', 'https://example.com/t/1', None))
        self.assertEqual(draft['desc'], 'רביעיית ג׳אז')

    def test_a_gated_link_is_a_community_link_not_a_ticket(self):
        draft, _ = intake.event_draft(intake.parse_form(GATED), '2026-10-21')
        self.assertEqual((draft['url'], draft['tickets'], draft['community']),
                         ('https://facebook.com/groups/x', None, 'https://facebook.com/groups/x'))

    def test_a_free_event_never_borrows_its_event_page_as_a_ticket_link(self):
        fields = {**intake.parse_form(EVENT), 'מחיר': 'חינם', 'קישור לכרטיסים': ''}
        draft, problems = intake.event_draft(fields, '2026-10-21')
        self.assertEqual(problems, [])
        self.assertEqual((draft['price_from'], draft['tickets']), (0, None))

    def test_free_is_zero_and_a_price_may_carry_a_shekel_sign(self):
        fields = intake.parse_form(EVENT)
        self.assertEqual(intake.event_draft({**fields, 'מחיר': 'חינם'}, '2026-10-21')[0]['price_from'], 0)
        self.assertEqual(intake.event_draft({**fields, 'מחיר': '₪80'}, '2026-10-21')[0]['price_from'], 80)

    def test_every_missing_required_field_is_named_in_form_order(self):
        draft, problems = intake.event_draft({'שם האירוע': 'ערב ג׳אז'}, '2026-10-21')
        self.assertIsNone(draft)
        self.assertEqual(problems, ['שם המקום', 'עיר', 'תאריך', 'שעה'])

    def test_a_bad_date_time_price_or_url_names_only_that_field(self):
        fields = intake.parse_form(EVENT)
        self.assertEqual(intake.event_draft({**fields, 'תאריך': '2026-02-30'}, '2026-10-21')[1],
                         ['תאריך (YYYY-MM-DD)'])
        self.assertEqual(intake.event_draft({**fields, 'שעה': '25:00'}, '2026-10-21')[1],
                         ['שעה (HH:MM)'])
        self.assertEqual(intake.event_draft({**fields, 'תאריך': '2026-10-20'}, '2026-10-21')[1],
                         ['תאריך שכבר עבר'])
        self.assertEqual(intake.event_draft({**fields, 'תאריך': '2150-01-01'}, '2026-10-21')[1],
                         ['תאריך רחוק מדי (עד 2100)'])
        self.assertEqual(intake.event_draft({**fields, 'מחיר': 'מאה שקל'}, '2026-10-21')[1],
                         ['מחיר (מספר בשקלים או חינם)'])
        self.assertEqual(intake.event_draft({**fields, 'קישור לאירוע': 'javascript:alert(1)'}, '2026-10-21')[1],
                         ['קישור לאירוע (https://)'])
        self.assertEqual(intake.event_draft({**fields, 'קישור לכרטיסים': 'javascript:alert(1)'}, '2026-10-21')[1],
                         ['קישור לכרטיסים (https://)'])

    def test_a_single_digit_hour_is_the_same_time_as_a_padded_one(self):
        fields = intake.parse_form(EVENT)
        draft, problems = intake.event_draft({**fields, 'שעה': '9:30'}, '2026-10-21')
        self.assertEqual(problems, [])
        self.assertEqual(draft['start'], 1794641400)      # 2026-11-14 09:30 IST

    def test_a_two_hundred_and_one_character_title_is_refused_not_truncated(self):
        fields = {**intake.parse_form(EVENT), 'שם האירוע': 'א' * 201}
        self.assertEqual(intake.event_draft(fields, '2026-10-21')[1], ['שם האירוע (עד 200 תווים)'])


class SourceTest(unittest.TestCase):
    def test_a_source_form_is_a_canonical_request(self):
        record, problems = intake.source_record(intake.parse_form(SOURCE))
        self.assertEqual(problems, [])
        self.assertEqual(record, {'name': 'בילום', 'url': 'https://biluim.co.il',
                                  'kind': 'aggregator', 'note': 'חסרים אירועים מחוץ לתל אביב'})

    def test_a_missing_url_and_an_unknown_kind_are_named(self):
        fields = intake.parse_form(SOURCE)
        self.assertEqual(intake.source_record({**fields, 'כתובת המקור': 'javascript:x'})[1],
                         ['כתובת המקור (https://)'])
        self.assertEqual(intake.source_record({**fields, 'סוג המקור': 'פודקאסט'})[1],
                         ['סוג המקור'])


if __name__ == '__main__':
    unittest.main()
