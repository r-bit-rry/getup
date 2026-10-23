"""Closed vocabulary and the committed label cache. No model call, no network, no key."""

import hashlib
import re

from . import write
from .normalize import desc_cap, norm_title

VOCAB = {
    'scene': ['רוק', 'פופ', 'מזרחית', 'אלקטרונית/טכנו', 'היפ הופ', 'ג׳אז', 'בלוז', 'קלאסי',
              'אינדי', 'מופע מחווה', 'סטנדאפ', 'תיאטרון', 'מחול', 'ילדים', 'ספורט'],
    'crowd': ['להט״ב', '18+', '30+', '40+', 'סטודנטים', 'משפחות', 'הורים', 'חיילים'],
    'format': ['live_band', 'tribute', 'dj_set', 'orchestra', 'standup', 'theatre', 'festival',
               'unknown'],
}

# Leaan's five categories are the only deterministic evidence a source gives. A genre it
# does not name is left unnamed rather than guessed.
RULES = {
    'מוזיקה': {'format': 'live_band', 'scene': [], 'crowd': []},
    'בידור וסטנדאפ': {'format': 'standup', 'scene': ['סטנדאפ'], 'crowd': []},
    'הצגות והרצאות': {'format': 'theatre', 'scene': ['תיאטרון'], 'crowd': []},
    'ילדים': {'format': 'unknown', 'scene': ['ילדים'], 'crowd': []},
    'ספורט': {'format': 'unknown', 'scene': ['ספורט'], 'crowd': []},
}

DESC_LIMIT = 200
KEY_RE = re.compile(r'^[0-9a-f]{16}$')


def key(rec: dict) -> str:
    return hashlib.sha1(norm_title((rec or {}).get('title')).encode('utf-8')).hexdigest()[:16]


def _list(value, axis: str) -> list[str]:
    if not isinstance(value, list):
        return []
    seen = []
    for item in value:
        if isinstance(item, str) and item in VOCAB[axis] and item not in seen:
            seen.append(item)
    return seen


def sanitize(label: dict) -> dict:
    label = label if isinstance(label, dict) else {}
    fmt = label.get('format')
    return {'format': fmt if isinstance(fmt, str) and fmt in VOCAB['format'] else 'unknown',
            'scene': _list(label.get('scene'), 'scene'),
            'crowd': _list(label.get('crowd'), 'crowd')}


def rules(rec: dict) -> dict:
    for tag in (rec or {}).get('tags') or []:
        if tag in RULES:
            return sanitize(RULES[tag])
    return sanitize({})


def load(root: str) -> dict:
    data = write.read_json(write.labels_file(root), {})
    if not isinstance(data, dict):
        return {}
    return {k: sanitize(v) for k, v in data.items() if isinstance(k, str) and KEY_RE.match(k)}


def save(root: str, labels: dict) -> bool:
    return write.write_json(write.labels_file(root), dict(sorted(labels.items())))


def pending(records: list[dict], labels: dict) -> list[dict]:
    batch = {}
    for rec in sorted(records or [], key=lambda r: key(r)):
        k = key(rec)
        if k in labels or k in batch:
            continue
        batch[k] = {'key': k, 'title': ' '.join(str(rec.get('title') or '').split()),
                    'desc': desc_cap(rec.get('desc'), DESC_LIMIT),
                    'tags': list(rec.get('tags') or [])}
    return [batch[k] for k in sorted(batch)]


def merge(labels: dict, replies: list[dict]) -> dict:
    merged = dict(labels or {})
    for reply in replies or []:
        if not isinstance(reply, dict):
            continue
        k = reply.get('key')
        if isinstance(k, str) and KEY_RE.match(k):
            merged[k] = sanitize(reply)
    return dict(sorted(merged.items()))


def apply(records: list[dict], labels: dict) -> list[dict]:
    out = []
    for rec in records or []:
        label = labels.get(key(rec)) or rules(rec)
        out.append({**rec, 'format': label['format'],
                    'scene': list(label['scene']), 'crowd': list(label['crowd'])})
    return out
