"""`data/human.json`: one canonical draft per issue number, committed and read on every run.

The file is not a day file: it never matches `^\\d{4}-\\d{2}-\\d{2}\\.json$`, so `write.data_files`,
`manifest.day_counts` and the client never enumerate it. It is opened by its exact path only.
"""

import os

from . import write

FILE = 'human.json'


def store_file(root: str) -> str:
    return os.path.join(root, 'data', FILE)


def load(root: str) -> dict:
    """Missing is empty; anything malformed raises and names the file — never a silent drop."""
    path = store_file(root)
    if not os.path.exists(path):
        return {}
    data = write.read_json_strict(path)
    if not isinstance(data, dict):
        raise ValueError(f'{path}: store is not an object')
    for key, draft in data.items():
        if not str(key).isdigit() or not isinstance(draft, dict):
            raise ValueError(f'{path}: {key!r} is not a draft keyed by issue number')
        if not isinstance(draft.get('title'), str) or not draft['title'].strip() \
                or not isinstance(draft.get('venue'), str) or not draft['venue'].strip() \
                or not isinstance(draft.get('start'), int) or isinstance(draft.get('start'), bool):
            raise ValueError(f'{path}: {key!r} is missing a title, a venue or a start')
    return data


def save(root: str, store: dict) -> bool:
    return write.write_json(store_file(root), store)


def records(store: dict) -> list[dict]:
    """The drafts themselves, ordered by integer issue number so a build cannot swap rows."""
    return [store[key] for key in sorted(store, key=lambda key: int(key))]


def put(store: dict, number: int, record: dict) -> bool:
    """Replace this issue's draft; True only when the value changed. A re-poll is the correction path."""
    key = str(number)
    if store.get(key) == record:
        return False
    store[key] = record
    return True
