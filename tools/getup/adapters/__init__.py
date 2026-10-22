"""The adapter table: one entry per source."""

from . import biluim, leaan, popit

ADAPTERS = {leaan.NAME: leaan, popit.NAME: popit, biluim.NAME: biluim}
