"""A stand-in for `github.Client`: no network, every write recorded."""


class Fake:
    def __init__(self, issues=(), comments=None):
        self.pending = list(issues)
        self.comments_ = dict(comments or {})
        self.said, self.labels, self.ensured = [], [], 0

    def ensure_labels(self):
        self.ensured += 1

    def issues(self):
        return list(self.pending)

    def comments(self, n):
        return list(self.comments_.get(n, []))

    def comment(self, n, body):
        self.said.append((n, body))
        self.comments_.setdefault(n, []).append({'body': body})
        return {}

    def add_label(self, n, name):
        self.labels.append((n, name))

    def remove_label(self, n, name):
        self.labels.append((n, '-' + name))


def issue(n, body, association='OWNER', labels=()):
    return {'number': n, 'state': 'open', 'body': body, 'author_association': association,
            'labels': [{'name': 'intake'}, *({'name': l} for l in labels)]}
