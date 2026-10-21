# ADR-0002: Serve 30 days of raw JSON; archive older data compressed, monthly

- **Status:** Accepted
- **Date:** 2026-10-18
- **Supersedes:** —
- **Superseded by:** —

## Context

Measured on 195 real records: 931 B/record with description. At 800 events/day that is
0.71 MB/day or 259 MB/year raw; at 2,000/day, 647 MB/year. GitHub's comfort limit sits near
1 GB, so raw retention gives roughly a two-year archive. The browser never fetches the
archive — only the next 30 days.

## Decision

`data/YYYY-MM-DD.json` holds one date, raw JSON, for the **next 30 days** only.
`data/index.json` is a manifest (dates present, counts, generated_at, coverage summary).
Anything older than 90 days rolls into `archive/YYYY-MM.json.zst`, monthly, full records.

Codec: zstd when available (`compression.zstd`, stdlib from Python 3.14 per PEP 784), falling
back to lzma (`compression.lzma`) because libzstd is an *optional* build dependency and may
be absent from an Android/proot build. Fallback is three lines.

## Consequences

Measured codecs on the real blob: xz 15,860 B (82.8% of gzip), zstd-19 16,256 B,
gzip 19,152 B. The 2.5% gap is noise; robustness of the fallback matters more.

Archived data is not greppable without decompression, and not diffable in git. Accepted:
it is machine-generated, write-once, and reviewed by no one.
