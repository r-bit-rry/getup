# GetUp — Design

Date: 2026-10-18
Status: DRAFT for approval. Supersedes nothing.
Scope: v1, personal radar. Everything here was decided in a brainstorming session on
2026-10-18; the decisions are also recorded as ADRs in `docs/adr/`. Where this document
and an ADR disagree, the ADR is newer and wins.

---

## 1. Intent and why

Israel's live-event information is fragmented across channels that each require you to
already be subscribed to them: ticketing platforms that sell weeks ahead, nightlife RSS
feeds, venue Instagram accounts, city aggregators, and gated Facebook/WhatsApp communities
that exist only to vet who joins. Following them is a manual chore — roughly thirty
Instagram accounts plus a resale group just to know what exists.

GetUp replaces that chore with one Hebrew, list-first page that answers four questions in
one glance: **what is it, what will it cost, who goes, and can I get there.**

The build is deliberately constrained: a static site on GitHub Pages, fed by a Hermes agent
running on an Android phone that scans sources daily and commits JSON. There is no server,
no database, no API keys, and no build step.

### The market shape that drives the design

Measured on 2026-10-18 across three Leaan genre pages (195 events, 41 cities):

- **Ticketing platforms sell the future, not tonight.** Zero Leaan events fell on the
  current day; the nearest was +3 days, the furthest +303.
- Nightlife sources (Popit, venue social, Secret TLV) are same-week, and Sunday nights are
  empty nationwide.
- Therefore a "today" default is empty on most weekdays. The default horizon is 7 days.
- Prices: min ₪39, median ₪129, p90 ₪199, max ₪250.
- Venue names are not identifiers: `היכל התרבות` appears in **16 different cities** and
  `בית יד לבנים` in two. "Culture Hall" is the standard municipal name in Israel.

## 2. Goals

1. One page that replaces the follow/join chore for a single user in Netanya.
2. Every event carries: when (with relative date), what, where (venue **and** city), price
   or free, scene, crowd, a ticket or community link, and the logistics note.
3. A **leave-by time** — start − drive − 30 min buffer — because that is the number that
   actually decides whether you go.
4. Distinguish a real show from a club night; flag the expensive; flag whether you can
   walk in last minute or must plan.
5. Two modes: table + map on desktop, one card per event on mobile.
6. Hebrew, RTL, mobile and desktop.
7. Adding a source or reporting an event is a GitHub issue.

## 3. Non-goals (v1)

- No accounts, no auth, no personalised profiles beyond `localStorage`.
- No push notifications or email digests.
- No report-back loop ("how did it go last time"). Deferred to a later iteration.
- No English UI, no language toggle, no translation of event content.
- No reviews, ratings, attendance counts or popularity data — no source provides them.
- No user-submitted events beyond the issue form.
- No native app, no offline/PWA, no real-time updates.
- No private or gated publication: the site is public and so is everything it renders.

## 4. Anti-goals

These are the failure modes that matter. A technically complete portal that hits any of
these has failed.

| Anti-goal | Why it kills the product | Mechanism in §7 |
|---|---|---|
| **Noise** — too many irrelevant events | The page becomes another channel to skim, i.e. the problem it was built to solve | Narrow defaults, relevance ordering, `prefs.json` never/always rules |
| **Missing high-profile events** | A silent false negative destroys trust faster than a wrong label | `notable` tag + weekly coverage alarm per major venue |
| **Not knowing where an event is** | Ambiguous venue names make an event unusable — you cannot decide to go | `venues.json` keyed on geocoded point; city always rendered; map pin |

## 5. Constraints

- **GitHub Pages, Free tier** ⇒ the repository must be public, and the published site is
  public regardless. No server-side code and no secrets **in the site**. The site makes no
  authenticated call of its own; its only runtime third-party calls are keyless (map tiles,
  OSRM).
- **The agent is the LLM user, not the site.** Classification (§7.5) runs on the agent host
  through the Hermes agent's existing model access — the same provider and credentials it
  already uses for everything else. This design adds no new key anywhere. "No API keys"
  applies to the delivered portal, not to the agent.
- **Repo size**: Pages comfort limit near 1 GB; served files must stay small.
- **No build step** (ADR-0001). The site is the repository. The agent commits JSON and the
  change is live.
- **Agent host**: Android phone, Python 3.14 (stdlib only where possible).
- **Politeness budgets**: Nominatim ~1 req/s, OSRM public router best-effort.
  `tile.openstreetmap.org` is not used (ADR-0010).
- **Hebrew first** (ADR-0009): `dir="rtl"`, no i18n layer.
- **Trust boundaries**: every external source is untrusted input. Parse defensively; a
  malformed record is dropped and logged, never published half-formed.

## 6. Where events come from

The source playbook lives in the `israeli-events` skill (`references/sources.md`) and is
reused, not reinvented. Classes and their role:

| Class | Examples | Transport | Role |
|---|---|---|---|
| Ticketing | Leaan, Eventim | curl (Leaan), egress/browser (Eventim) | Canonical records for ticketed shows |
| Aggregators | Biluim, Bonire, Tickchak, Sababa, Mevalim | curl | Coverage + free events + enrichment |
| Nightlife | Popit RSS, ZYGO, RA | curl | Tonight and this week |
| Venue sites | Levontin 7, Ozen, Barby, Zappa, Gagarin | curl | Small-room shows |
| Social / mirrors | somo, allevents, secrettlv.app, Instagram, Facebook | egress/browser | Free events and the long tail |
| Human | GitHub issues | git | Gated communities, corrections, new sources |

Dead: `venues-israel.com` and its `/api/*`.

**Where the playbook lives.** The per-source recipes are not in this repository. They live
with the agent, as the `israeli-events` skill (`references/sources.md`), because they are
agent operating knowledge rather than site content. This design reuses them and does not
duplicate them. A copy may be vendored here for reference, but the skill on the agent host
is authoritative.

**The venue seed does not exist yet.** There is no committed list of venues; §7.3's registry
must be bootstrapped from the venue names the first scan produces, plus the seeded
venue-to-social map in the skill. Treat this as real work, not a lookup.

---

## 7. Design

### 7.1 Repository layout

GitHub Pages serves from the branch root.

```
index.html            the portal
app.js  styles.css    vanilla ES modules, hand-written token CSS
data/2026-10-23.json  one file per date, served horizon only
data/index.json       manifest: dates present, counts, generated_at, coverage summary
venue/venues.json     venue registry — identity, city, point, parking, access, social
archive/2026-08.json.zst   monthly, older than 90 days
prefs.json            never / always show rules, hand-edited
assets/               vendored maplibre-gl + self-hosted fonts
docs/                 this spec, ADRs, mockups
tools/                agent-side scan/normalize/derive scripts (run on the phone)
.github/ISSUE_TEMPLATE/  intake forms
```

### 7.2 Event record

One record per event. Written by the agent, never by the browser.

```jsonc
{
  "id": "v_zappa_tlv|2026-10-23|21:30",   // stable, see 7.4
  "title": "MADONNA THE TRIBUTE SHOW",
  "venue_id": "v_zionist_america_tlv",
  "city": "תל אביב",
  "start": 1792780200, "end": 1792787400,

  "price_from": 174, "price_max": 250,
  "free": false, "free_until": null,       // "חינם עד 22:00"
  "soldout": false,

  "format": "tribute",        // live_band|tribute|dj_set|orchestra|standup|theatre|festival|unknown
  "scene": ["פופ", "מופע מחווה"],
  "crowd": ["30+", "להט״ב"],
  "daypart": "night",         // day <17:00 | evening 17–20 | night >=20

  "expensive": false,         // >= p90 of the retained 30-day set, or >= ₪200 absolute
  "notable": true,            // see 7.6
  "commitment": "jump_in",    // jump_in | plan_ahead, see 7.6

  "source": { "class": "ticketing", "name": "leaan" },
  "urls": { "tickets": "...", "community": null, "source": "..." },
  "notes": ["שער פתיחה 20:30", "חניה חופשית במתנ״ס"],
  "desc": "…",
  "enrichment": [{ "source": "biluim", "note": "…" }],
  "seen": { "first": "2026-09-20", "last": "2026-10-18" }
}
```

Age restriction is deliberately **absent** as a required field. Where a source states it, it
arrives as a tag in `crowd` (`18+`). Where it does not, there is no tag — and per ADR-0006
that absence never removes the event from results.

### 7.3 Venue registry (`venues.json`)

The single source of truth for place identity. Events reference `venue_id`; they never
carry an authoritative venue string.

```jsonc
{
  "id": "v_zionist_america_tlv",
  "name": "בית ציוני אמריקה (מאירהוף)",
  "aliases": ["בית ציוני אמריקה", "Zionist America House"],
  "city": "תל אביב",
  "lat": 32.0771, "lon": 34.7753,
  "tier": "major",            // major | mid | room   (drives coverage alarm + notability)
  "parking": "חניון מאירהוף, ₪30/שעה",
  "access": "נגיש לכיסא גלגלים",
  "transport": "קו 5 מתחנה מרכזית",
  "social": { "instagram": "…", "facebook": "…" }
}
```

Geocoding happens **once per venue**, in the `"venue, city"` form the skill verified, and
the result is cached here forever. This is also what collapses `פתח תקווה` / `פתח תקוה` and
resolves `היכל התרבות` into distinct venues per city (ADR-0004).

### 7.4 Identity and dedup

- `venue_key` = the venue registry id, resolved from a normalized string plus city.
- Merge two records when `venue_key` matches **and** start times are within **±30 minutes**.
- Never merge on overlapping time windows alone. A club night 22:00–04:00 and a DJ set
  23:00–01:00 at the same venue are two rows; a noon party 12:00–20:00 and a night party
  21:00–03:00 differ by nine hours at the start and stay separate (ADR-0003).
- **Ticketed events**: the ticket seller owns the record. An aggregator's copy never becomes
  a second row — it is attached as `enrichment` (its description, parking/accessibility
  notes, crowd hints are often richer than the seller's). If no seller record exists yet,
  the aggregator record stands, marked `source.class = "aggregator"`, and is overridden
  when that seller is scanned.
- Free events merge across sources on the rule above.

### 7.4.1 Time bucketing

Everything is `Asia/Jerusalem`; unix timestamps from sources render in that zone and Hebrew
prose dates are pinned to it explicitly.

An event belongs to the calendar date of its **start**, with one exception: a start between
**00:00 and 05:59** is attributed to the **previous** day. A club night opening 23:00 Friday
and ending 04:00 Saturday is Friday night — that is how it is experienced and how it is
announced, and the Friday file is where a user looking for "tonight" will look. Getting this
wrong silently misfiles every after-midnight event, which is most of the nightlife tier.

### 7.5 Derived signals

Three of the things the user asked for have no source. They are computed at ingest by the
agent and **cached in the JSON**, never computed in the browser:

| Signal | Rule |
|---|---|
| `daypart` | from start hour: day <17:00, evening 17:00–19:59, night ≥20:00 |
| `expensive` | price ≥ p90 of the **retained 30-day set** (recomputed each scan, so the threshold is deterministic within a run), or ≥ ₪200 absolute. Never computed against the filtered view. |
| `free_until` | parsed from prose (`חינם עד 22:00`, `free before 11pm`) |
| `commitment` | `plan_ahead` if any: festival/rave format · drive ≥ 60 min · fixed-seat venue (theatre, orchestra). Else `jump_in`. The "ticketed and >48 h away" clause was removed (2026-10-22): in a 7-day window it is true of every ticketed event, so it carries no information. |
| `format` | LLM classification of title + description, from the fixed vocabulary in 7.7 |
| `notable` | §7.6 |

**On "a proper concert vs a mediocre DJ":** taste is not derivable and the system will not
pretend otherwise. What is derivable is `format`, and format is the honest proxy. A listing
on a ticketing platform with a named act is a show; a club-night entry off a nightlife feed
is a DJ set. The portal labels format. It never labels quality.

### 7.6 Notability and the coverage alarm

Leaan exposes no popularity signal at all — `promoted`, `last_hour_views`, `special_event`
and `subscription` were false or zero across every sampled event. So `notable` is composed:

```
notable = source.class == "ticketing"
      AND ( touring >= 2 cities            // 30 of 53 distinct titles tour; MAD MOZART tours 7
         OR venue.tier == "major"
         OR price_from >= 200 )
```

Touring is detected across the current data set by matching normalized titles.

The **coverage alarm** addresses the missed-event anti-goal directly: `tools/coverage.py`
reads `venues.json`, and for every venue with `tier = "major"` reports whether any event
referencing it was seen in the last 14 days. Misses are written into `data/index.json` and
surfaced as a single quiet line in the portal footer — never as a filter, never as an
interruption. A big venue going silent for two weeks is almost always a broken adapter, not
a quiet month.

### 7.7 Vocabulary

Fixed, closed lists. Everything else is dropped rather than invented.

- **scene** — רוק, פופ, מזרחית, אלקטרונית/טכנו, היפ הופ, ג׳אז, בלוז, קלאסי, אינדי,
  מופע מחווה, סטנדאפ, תיאטרון, מחול, ילדים, ספורט
- **crowd** — להט״ב, 18+, 30+, 40+, סטודנטים, משפחות, הורים, חיילים
- **format** — live_band, tribute, dj_set, orchestra, standup, theatre, festival, unknown

Leaan's own categories (מוזיקה, בידור וסטנדאפ, הצגות והרצאות, ילדים, ספורט) map into `scene`.

### 7.8 Ordering

Within a day: `notable` first, then ascending drive time. Days ascending. There is no
relevance score to tune — the ordering is explainable in one sentence, which matters more
than an arbitrary weight vector.

Noise control, in order of effect:
1. Defaults: 7-day horizon, ≤45 min drive.
2. Ordering above.
3. `prefs.json` — `never` / `always` rules keyed on venue or artist. Three curated venue
   entries remove more noise than any scoring model, and they converge instead of drifting.

### 7.9 Intake via GitHub issues

Two YAML issue forms: `אירוע חדש` and `מקור חדש`. Both auto-apply the `intake` label.

- The agent polls `label:intake -label:processed` daily.
- **Guard: only issues whose `author_association` is `OWNER` or `MEMBER` are processed.**
  The repo is public and anyone can file.
- On success the agent comments a receipt containing the canonical record and applies
  `processed`.
- On failure it comments what is missing, applies `needs-info`, and leaves the issue open.
  An issue is never half-ingested.
- Gated communities (Facebook groups, WhatsApp circles) are ordinary events with a
  `urls.community` link. Per ADR-0008 these communities are public and vetted, not private,
  so their links are published alongside ticket links.

### 7.10 Filters

| Filter | Behaviour |
|---|---|
| date | **השבוע (7 days) default**; היום / מחר / טווח, up to 30 days served |
| price | free-only toggle; max price slider (₪39–₪250 real range) |
| distance | max drive time in minutes from centre (default Netanya), not km |
| age | only ever **removes** an event when a source explicitly states an excluding restriction. Unknown never hides. |
| ticket availability | binary, only where a source reports it (Leaan `is_soldout`) |
| gated community | on/off — whether events requiring group membership are shown |
| scene / crowd | chips from §7.7 |

### 7.11 Client

Vanilla ES modules. No framework, no bundler, no `node_modules` (ADR-0001).

- Filter state and centre persist in `localStorage`.
- Centre defaults to Netanya; `navigator.geolocation` overrides when granted.
- **Drive time follows the centre.** Each record carries `lat`/`lon`, so when the centre is
  the default (Netanya) the client uses the `drive_min` cached at ingest. When the user
  geolocates or changes the centre, the client issues **one** keyless OSRM `/table` request
  for the visible result set and recomputes every distance, caching the result for the
  session. If that request fails, the cached Netanya minutes remain and the UI says the
  distances are relative to Netanya rather than silently showing wrong numbers.
- `prefs.json` is fetched and applied **in the browser**, at filter time. It is a user
  preference, not derived data, so ADR-0007 does not apply. Editing a rule takes effect on
  reload with no rescan.
- The footer renders **data age** from `data/index.json`'s `generated_at` ("עודכן לפני 3
  שעות"). This is the liveness signal: a dead or hung agent shows up as a stale timestamp
  rather than as silent staleness. No monitoring infrastructure.
- Desktop: sticky filter bar, single table with `table-layout: fixed` and a declared
  `<colgroup>`, map pane 38% sticky.
- Mobile: one card per event, swipeable list, tap toggles the full view (notes revealed).
  Chip strip caps at 3 with `+N`; icon **and** Hebrew label, never icon alone.
- The map is MapLibre GL 6 + OpenFreeMap (`positron`-like light base) with `text-field`
  forced to `["coalesce", ["get","name:he"], …]`. MapLibre ≥5 does its own bidi, so Hebrew
  renders correctly without the deprecated RTL plugin.

### 7.12 Design system

| | |
|---|---|
| Type | **Rubik** variable — one family covering Hebrew and Latin, tabular numerals. **Secular One** for the wordmark only. |
| Colour | `#EA580C` events, `#2563EB` map/cool, `#FFF7ED` day base, `#0B1120` night base. Dark text on orange (black-on-orange ≈6.3:1). |
| Density | 40 px rows, 13 px body, 11 px chips, 8 px spacing base. |
| Hierarchy | **Not uppercase micro-labels.** Hebrew has no uppercase, so Latin label systems do not translate; hierarchy is weight + size + colour. |
| Chips | Two axes, two colours: scene blue, crowd orange. |

Reference concept: `docs/design/mockup-01-getup.html` (real data, real OSRM drive times).

---

## 8. Data pipeline (agent side)

```
scan   → per-source adapters, honouring per-source transport rules
normalize → venue_key resolution, city normalization, city spelling collapse
dedup  → §7.4
derive → daypart, expensive, free_until, commitment, format, notable, seen counters
write  → data/YYYY-MM-DD.json for the next 30 days + data/index.json
archive→ monthly, older than 90 days, compressed (ADR-0002)
commit → git push; Pages serves the new JSON with no build
```

Cadence: **daily**, initially. Idempotent — re-running on unchanged sources must produce
byte-identical output, so the agent can be retried safely.

**Window and state.** Three different windows, and conflating them breaks either freshness or
the alarm:

| Window | What it governs |
|---|---|
| **Full source payload** (Leaan reaches +303 days) | read by the scan; used for tour detection and `notable`. Nothing beyond the horizon is stored. |
| **30-day horizon** | what is written to `data/` and served. |
| **90-day raw** | what stays uncompressed before rolling into `archive/`. |
| **14 days** | the coverage-alarm lookback per major venue. |

There is **no state store.** Everything the agent needs across runs is recomputed by reading
the committed `data/` and `archive/` files: `seen.first`/`seen.last`, recurrence, and
dedup against previous days. The repository is the only state, which is what keeps the
idempotency requirement satisfiable and the phone stateless. `seen.count` was dropped from
§7.2 for exactly this reason — scan counts are not recoverable from committed files, and a
field that cannot be reproduced cannot be trusted.

`expensive`'s p90 denominator is the retained 30-day set recomputed each scan; it is a
property of the run, not of the user's filters.

---

## 9. Decisions taken (see `docs/adr/`)

| ADR | Decision |
|---|---|
| 0001 | Public repo, GitHub Pages from branch root, **no build step**, vanilla ES modules |
| 0002 | Serve 30 days of raw per-date JSON; archive older as monthly compressed files |
| 0003 | Dedup: venue identity + start within ±30 min; never merge on overlap alone |
| 0004 | `venues.json` registry keyed on geocoded point is the only place identity |
| 0005 | Ticket seller owns ticketed records; aggregator copies become enrichment |
| 0006 | Unknown never hides an event; only an explicit source contradiction does |
| 0007 | Derived signals computed at ingest and cached, never in the browser |
| 0008 | Everything is public, including gated-community links |
| 0009 | Hebrew-first, `dir="rtl"`, no i18n layer |
| 0010 | MapLibre GL 6 + OpenFreeMap; OpenStreetMap's own tiles rejected |
| 0011 | Design system: Rubik + Secular One, orange/blue, dense rows, two-colour chip axes |
| 0012 | Notability composed from touring × venue tier × price; weekly coverage alarm |

## 10. Left to the builder

- Per-source adapters and parse recipes (start from the `israeli-events` skill's
  `references/sources.md`; the skill is authoritative, §6).
- **Verify each source still speaks the transport the skill assumes.** The skill's own
  example: Eventim refuses terminal curl, Leaan is curl-friendly. This verification is the
  largest hidden cost in the plan.
- The classification prompt for `format` / `scene` / `crowd` against the closed vocabulary,
  and its few-shot seed. Batched per scan.
- Bootstrap `venues.json` from the venue names the first scan produces, plus the skill's
  seeded venue-to-social map: geocode, resolve aliases, assign `tier`. **Real work — no
  venue list is committed yet.**
- Geocode cache and Nominatim rate limiter.
- `prefs.json` schema and how a never/always rule is authored (issue form vs hand edit).
- Coverage-alarm thresholds (14 days is a starting guess; `tier` needs calibration against
  real weeks). A noisy alarm is worse than no alarm.
- Scheduler, git credentials and doze-survival on the phone host. The design does not
  specify a runtime; the liveness signal (§7.11, data age in the footer) is what keeps a
  dead agent visible. Out of scope here, but it must exist before the daily cadence is real.
- The empty state copy for quiet weekdays.
- Deferred: report-back loop, English UI, dark map base style, PWA/offline.
