# Research capture — 2026-10-21

Raw evidence behind the design doc and the plan fixtures. Committed so it survives `/tmp`
being cleared (the original 2026-10-18 capture did not).

- `leaan-events.json` — 215 events extracted from three Leaan genre category pages
  (`__NEXT_DATA__` → `props.pageProps.initialState.pageData.events[]`). Fields kept:
  event_id, title, venue, city, street, start/end (unix), price, multi_price, soldout,
  categories, description (400 chars), url.
- `popit.xml` — Popit RSS, 60 items.
- `geo-drive.json` — Nominatim geocodes for 29 of 43 cities (the rest have no alias), plus
  OSRM driving distance and duration **from Netanya** for each. Origin is Netanya per the
  spec.

Re-measured on this capture, confirming the design doc's claims from 2026-10-18:

| Claim | 2026-10-18 | 2026-10-21 |
|---|---|---|
| events | 195 | 215 |
| cities | 41 | 43 |
| `היכל התרבות` distinct cities | 16 | 17 |
| price p90 | ₪199 | ₪199 |

Drive times are stable: Netanya→Tel Aviv 31.6 km / 29 min, →Haifa 64.6 / 53, →Jerusalem
94.3 / 79, →Beer Sheva 131.9 / 106.

The raw HTML pages (~8 MB) were deleted after extraction; re-fetch the category URLs listed
in the `israeli-events` skill's `references/sources.md` to regenerate.
