"""Venue-and-time dedup: the seller owns the row, the other sources only enrich it.

ADR-0003: two records are one event only when the venue matches and the starts are
within ±30 minutes. Overlapping windows alone never merge, because a club night and
a DJ set inside it at the same venue are two real rows.
"""

import copy

from .normalize import norm_title

WINDOW = 1800
RANK = {'ticketing': 3, 'aggregator': 2, 'nightlife': 1}
NOTE_LIMIT = 200


def _source(rec: dict) -> dict:
    return rec.get('source') or {}


def _rank(rec: dict) -> int:
    return RANK.get(_source(rec).get('class'), 0)


def _name(rec: dict) -> str:
    return str(_source(rec).get('name') or '')


def _key(rec: dict) -> tuple:
    """The tie-break that makes input order irrelevant: title form, then id."""
    return (norm_title(rec.get('title')), str(rec.get('id') or ''))


def enrichment_note(loser: dict) -> str:
    """What a merged copy is still worth saying: its source and its own words."""
    urls = loser.get('urls') or {}
    body = ' '.join(str(loser.get('desc') or '').split())
    body = body or str(urls.get('source') or '') or str(urls.get('tickets') or '')
    if not body:                    # nothing to say: no label beats an empty one
        return ''
    note = f'{_name(loser)}: {body}'
    return note if len(note) <= NOTE_LIMIT else note[:NOTE_LIMIT - 1].rstrip() + '…'


def _absorb(winner: dict, loser: dict) -> None:
    """The loser's facts move onto the winner; nothing of the winner is overwritten."""
    if _name(loser) != _name(winner):
        note = enrichment_note(loser)
        if note and note not in winner['enrichment']:
            winner['enrichment'].append(note)
    for note in loser.get('enrichment') or []:
        if note not in winner['enrichment']:
            winner['enrichment'].append(note)
    if not winner['urls'].get('community') and loser['urls'].get('community'):
        winner['urls']['community'] = loser['urls']['community']
    for note in loser.get('notes') or []:
        if note not in winner['notes']:
            winner['notes'].append(note)


def _wins(candidate: dict, current: dict) -> bool:
    if _rank(candidate) != _rank(current):
        return _rank(candidate) > _rank(current)
    return _key(candidate) < _key(current)


def merge(records: list[dict]) -> list[dict]:
    """One row per event: sorted so a re-run cannot swap the winner or the order."""
    groups = {}
    for rec in records if isinstance(records, list) else []:
        if isinstance(rec, dict):
            groups.setdefault(rec.get('venue_id'), []).append(copy.deepcopy(rec))

    kept_all = []
    for venue_id in sorted(groups, key=str):
        kept = []
        for rec in sorted(groups[venue_id],
                          key=lambda r: (r.get('start') or 0, _key(r), _name(r))):
            last = kept[-1] if kept else None
            if last is not None and abs((rec.get('start') or 0) - (last.get('start') or 0)) <= WINDOW:
                if _wins(rec, last):
                    _absorb(rec, last)
                    kept[-1] = rec
                else:
                    _absorb(last, rec)
                continue
            kept.append(rec)
        kept_all.extend(kept)

    return sorted(kept_all, key=lambda r: (r.get('start') or 0, str(r.get('id') or '')))
