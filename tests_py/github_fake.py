"""A stand-in for `github.Client`: no network, every write recorded."""


class Fake:
    def __init__(self, issues=(), comments=None, states=None):
        self.pending = list(issues)
        self.states = dict(states or {})
        self.comments_ = dict(comments or {})
        self.said, self.labels, self.ensured = [], [], 0
        self.lookups = []                   # every issue number the retraction asked about

    def ensure_labels(self):
        self.ensured += 1

    def issues(self):
        return list(self.pending)

    def issue(self, n):
        self.lookups.append(n)
        return {'number': n, 'state': self.states.get(n, 'open')}

    def comments(self, n):
        return list(self.comments_.get(n, []))

    def comment(self, n, body):
        self.said.append((n, body))
        self.comments_.setdefault(n, []).append(
            {'body': body, 'author_association': 'OWNER',
             'user': {'login': 'getup-bot', 'type': 'Bot'}})
        return {}

    def add_label(self, n, name):
        self.labels.append((n, name))

    def remove_label(self, n, name):
        self.labels.append((n, '-' + name))


def issue(n, body, association='OWNER', labels=()):
    return {'number': n, 'state': 'open', 'body': body, 'author_association': association,
            'labels': [{'name': 'intake'}, *({'name': l} for l in labels)]}
