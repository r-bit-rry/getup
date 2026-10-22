"""The adapter table: one entry per source."""

from . import leaan, popit

ADAPTERS = {leaan.NAME: leaan, popit.NAME: popit}
