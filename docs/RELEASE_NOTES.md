# Accidental Scientist: Release Notes

## Thesis

These notes exist to make a claim falsifiable, not to describe a change in adjectives. "Improved" and "redesigned" tell a reader nothing they could check; a formula, a function name, or a before-and-after number does. Every entry should state what was true of the system before the change and after it, and the mechanism that moved it — because the mechanism is the only part that proves the work happened rather than merely occurred. A patch note states what changed; a release note explains why it mattered. This document refuses that split — every entry states both, because a change without its reason attached is a fact with no way to judge whether it was a good one.

This project has one real reader — the author, later, or someone verifying the engineering was genuine — closer to a competitive game's patch-note audience than to an enterprise customer, so precision is the default, not the exception. That precision extends to naming a coupled change — resizing X that forced a change in Y — whenever the coupling itself is the information; it stops at inventorying every touched file, which restates a diff without explaining it.

Every entry is ordered problem, then solution, then reason — stated in a clause, worked through in detail, and closed only if the reason isn't already obvious from the problem. That order guides the writing; it is never labelled on the page. A change with no real problem behind it — a pure addition — skips straight to the solution rather than manufacturing one to fit the shape.

`MAJOR.MINOR.PATCH`: **Major** — entire-site redesign or incompatible architecture change. **Minor** — a new project or a substantial user-facing capability. **Patch** — a visual, copy, bug, or operational fix. Every deployed change gets a version; the tag is always identical to the version number.

## Release themes at a glance

| Version | Theme | Date |
|---|---|---|
| 2.8.5 | The contact form gains a validated keyboard-send shortcut | Unreleased |
| 2.8.4 | Branded mail routing, HTTPS contact delivery, and a portal-themed confirmation page | 17 Aug 2026 |
| 2.8.3 | Portfolio Pulse gains account trend modelling and behavioural archetypes; World Ledger doubles its pillar count | 14 Aug 2026 |
| 2.8.2 | StillPoint's interval bells become randomized; Life Compass gets its first post-launch design pass | 13 Aug 2026 |
| 2.8.1 | The automated NEM refresh becomes weekly and memory-bounded | 11 Aug 2026 |
| 2.8.0 | FlowTrace and ChargeTrace launch inside one unified, automatically refreshed NEM suite | 11 Aug 2026 |
| 2.7.15 | NEM Price Predictor Lab MVP ships; Life Compass and World Ledger get visual passes | 6 Aug 2026 |
| 2.7.14 | StillPoint fully redesigned visually; Portfolio Pulse gains three selectable scoring models | 4 Aug 2026 |
| 2.7.13 | Portfolio Pulse rebuilt around three decision views and ARR-only language | 30 Jul 2026 |
| 2.7.12 | StillPoint's background-tab completion bug fixed; renamed to StillPoint | 30 Jul 2026 |
| 2.7.11 | Life Compass execution page overhauled: ledger toggle, kanban aging, X Calendar, Pomodoro | 30 Jul 2026 |
| 2.7.10 | Article image crop bug fixed | 17 Jul 2026 |
| 2.7.9 | Life Compass gets its parchment/brass visual identity; dependency cleanup; contact form silent-failure fixed | 14 Jul 2026 |
| 2.7.8 | Life Compass execution workflow: earned calendar marks, project-derived daily tasks | 13 Jul 2026 |
| 2.7.7 | Life Compass goes private: session auth, per-user sync | 8 Jul 2026 |
| 2.7.6 | Life Compass and Portfolio Pulse added as new projects | 7 Jul 2026 |
| 2.7.5 | Public category taxonomy settled on Commercial Intelligence | 28–30 Jun 2026 |
| 2.7.4 | Tagline, admin, and typewriter copy refinements | 27 Jun 2026 |
| 2.7.3 | The running site version becomes publicly visible | 27 Jun 2026 |
| 2.7.2 | CSS split into source partials, bundled by django-compressor for production | 27 Jun 2026 |
| 2.7.1 | Footer, decorative identity, and mobile navigation polished | 27 Jun 2026 |
| 2.7.0 | Contact reliability, production security headers, and search metadata added | 26 Jun 2026 |
| 2.6.0 | StillPoint launches; NEM Dashboard reframed around an honest 7-day window | 25 Jun 2026 |
| 2.0.0 | The Austro-Indo-French visual identity replaces the original Bootstrap-default look | 24 Jun 2026 |
| 1.4.2 | Stray Windows-only dependency removed | 6 Aug 2025 |
| 1.4.1 | Unused image asset removed | 6 Aug 2025 |
| 1.4.0 | First NEM dashboard ships: a basic Chart.js bar chart | 4 Aug 2025 |
| 1.3.1 | Blog image and dark-mode display fixes | 28 Jul 2025 |
| 1.3.0 | Markdown rendering and multi-image articles added | 26 Jul 2025 |
| 1.2.1 | Broken LinkedIn link fixed | 11 Jun 2025 |
| 1.2.0 | First blog/site presentation overhaul; card-style post list | 10 Jun 2025 |
| 1.1.3 | Wagtail dependency removed; Willow downgraded | 2 May 2025 |
| 1.1.2 | README project overview written | 24 Apr 2025 |
| 1.1.1 | Settings moved to environment variables; seed data added | 17 Apr 2025 |
| 1.1.0 | Blog, projects, contact form, and dark mode added | 16 Apr 2025 |
| 1.0.0 | Initial Django scaffold | 11 Apr 2025 |

---

## 2.8.5: contact.html validated keyboard submission (Unreleased)

- Contact messages previously required a pointer interaction with the submit button. Pressing **Ctrl + Shift + Enter** anywhere inside the form now requests submission through the browser's native form pipeline, so the same required-field and email-format checks run for the shortcut and the button.
- An incomplete shortcut attempt calls `reportValidity()` and stays on the form, exposing the browser's validation prompt instead of posting partial content. A valid submission disables the button and changes its label to **Sending…**, preventing accidental duplicate posts while the request is in flight.
- The shortcut is printed beside the submit button and declared through `aria-keyshortcuts="Control+Shift+Enter"`, making the alternative interaction visible to sighted users and available to assistive technology without changing the ordinary button workflow.
- Local release evidence is complete for commit `5798122`: all 291 Django tests passed, Django reported no model drift or system-check issues, and a real browser shortcut attempt with only the name populated stayed on `/about/` with `email` and `message` still invalid. Production verification remains pending until `v2.8.5` is tagged and deployed.

## 2.8.4: branded mail routing, Resend delivery, and message-sent page (17 August 2026)

- Gmail SMTP succeeded in local development but contact submissions from the DigitalOcean Droplet waited for a connection that could never complete because the platform blocks outbound SMTP ports. Website notifications now use Resend's HTTPS API with the verified `hello@accidentalscientist.net` sender, the visitor's address as Reply-To, a ten-second timeout, and a stable idempotency key per saved contact.
- Incoming and outgoing responsibilities are deliberately separate. The root-domain MX records remain on ImprovMX at priorities 10 and 20 so mail addressed to `hello@accidentalscientist.net` forwards to the private mailbox. Resend receiving stays disabled; its DKIM TXT record and `send`-subdomain SPF TXT and feedback MX authenticate website-generated mail without replacing the root inbound route.
- Production configuration now contains only `RESEND_API_KEY`, `CONTACT_EMAIL`, and `DEFAULT_FROM_EMAIL` for the contact path; obsolete Gmail SMTP variables were removed. The application knows only the public alias, while the private destination remains inside ImprovMX. This does not configure general-purpose Gmail **Send mail as** behaviour; it authenticates messages generated by the website and preserves inbound forwarding.
- A valid submission is written to the `Contact` table before its notification is attempted. If Resend is unavailable, the message therefore remains recoverable and the form shows a real failure instead of claiming success or discarding the content.
- Successful submissions redirect to a stable `/about/message-sent/` page. Its portal animation honours reduced-motion preferences, responds cleanly on mobile and in dark mode, and offers exactly two next actions: the primary green **Explore Infinite Energies** route into the NEM Dashboard, or **Return to Dimension C-137** back to About.
- Production ran the exact `v2.8.4` artifact at commit `0bd2892`: Gunicorn restarted active, database and Django checks passed, six public route probes returned successfully, the visible version marker and new success-page copy were present, and an end-to-end form submission reached the destination mailbox. The production environment file was restricted to owner-only permissions during the same deployment audit.

## 2.8.3: Portfolio Pulse trends and archetypes; World Ledger Giga v2.0 (14 August 2026)

- Retention Horizon's score reflected an account's current state but nothing about its trajectory. Each account now gets an ordinary-least-squares trend line fitted across up to its last 13 monthly data points (adoption, ARR, ticket volume), producing a small, individually capped point adjustment on top of the existing Signal Compass score — a declining adoption trend can cost at most 8 points, a declining ARR trend at most 6 — scaled down for short histories, so a two-month-old account can't generate a confident-looking trend from noise.
- Nothing grouped accounts by behaviour independent of their health score. Account Archetype Fingerprint adds deterministic k-means clustering into 3–5 behavioural archetypes using five normalized signals: adoption level, adoption momentum, ARR momentum, support position, engagement position. Health score and account identity are excluded from the fit, so a cluster reflects behaviour rather than restating a score computed elsewhere; each cluster is matched to a plain-English label ("Silent Erosion," "Established Compounders") by comparing its shape against a small set of declared signatures.
- Revenue concentration was only visible as a single day's snapshot. Revenue Breadth re-ranks positive-ARR accounts independently every month and tracks what share of total ARR the top 1, 5, and 10 accounts hold, turning concentration into a visible trend.
- World Ledger's Giga Dataset moved from 5 to 10 pillars per model — Power Now adds Energy, Logistics, Finance, Global leverage, Technology; Power Potential adds Institutions, Innovation investment, Energy transition. The extra pillars pushed a handful of previously-qualifying economies below the cutoff, so the comparison cohort widened from 48 to 60. A new estimation method fills remaining gaps: check the country's own historical value for that indicator, build a peer group of same-region economies ranked by GDP-per-capita closeness (at least 3 real peers required or the estimate is skipped), then project the country's own trend forward using the peer group's trajectory or fall back to the peer average — every estimated figure is flagged and excluded from the mean/standard-deviation calculation used to score everyone else, so one country's estimate can't move another country's rank.
- A military-resourcing panel was added, deliberately unscored: spend and personnel from public World Bank data, arms-export value pulled live from SIPRI's backend API, shown only as context for selected countries, never folded into a ranking.
- The `v2.8.3` marker was confirmed live on 16 August. Its annotated tag points to `39f2fd4`, while production also contained the follow-up `6426fd8` military-data update without moving the tag; the release ledger records that historical artifact mismatch explicitly. Exact tag-to-production identity was restored for `v2.8.4` and remains a release requirement.

## 2.8.2: StillPoint ring scale, interval-bell randomization, dial controls; Life Compass execution layout (13 August 2026)

- Growing the session ring larger only works if the page can't scroll while it's shown, or the enlarged ring breaks the layout. In `static/css/stillpoint.css`, running-session ring max size raised to `74vw` / `68vh`; `body` given `overflow: hidden` for the session's duration, added in the same change.
- A single interval-bell recording played identically at every two-minute mark across a session. In `stillpoint/static/stillpoint/js/timer.js`, 3 new bowl recordings were decoded into `intervalBowlBuffers` via `loadIntervalBowls()` (`AudioContext.decodeAudioData`); a new `intervalBell()` picks one at random — `intervalBowlBuffers[Math.floor(Math.random() * intervalBowlBuffers.length)]` — at gain peak `0.5`, versus `0.9` for the original recording, now reserved for the start/end chime, and falls back to the existing synthesized `softBell()` if buffers aren't decoded yet. Repeats are allowed on purpose — variation across a long sit, not a rotation a listener could learn.
- The five duration-preset buttons and related controls used generic app-button styling. In `stillpoint/templates/stillpoint/timer.html`, the 5 `<button class="sp-duration">` elements were replaced with `.sp-calmark` marks on an SVG arc plus paired `.sp-calibration-line` elements (shared `data-min` lookup); `#sp-begin` lost its button class for plain text; `.stillpoint__mode` toggle lost its filled-background class for underlined text.
- North Star sat inline as a fourth item inside the same grid as the three weekly-focus fields, despite being durable information rather than a weekly one. In `life_compass/templates/life_compass/execution.html`, split into `.focus-strip-columns` with two sibling `.focus-strip-group` divs; `.daily-panel` and `.ledger-panel` wrapped in a new `.panel-cluster`; each focus field gets a paired `.focus-strip-display` span for read-only rendering.
- 4 new PNG hero images added to `life_compass/static/life_compass/assets/` (`bireme_following_nightsky`, `bireme_journey`, `bireme_landfall_athens`, `star_compass`).
- The later production-verified `v2.8.3` deployment contained all `v2.8.2` changes, so the release ledger records `v2.8.2` as superseded by a verified artifact rather than as the current live version.

## 2.8.1: the NEM refresh becomes reliable on a 1 GB server (11 August 2026)

- AEMO's nested dispatch archives expand sharply once parsed in Python, and the battery-data refresh downloaded and parsed an entire requested date range in one pass; a multi-day catch-up run could exceed the production droplet's 1 GB of RAM and fail partway through. Restructured into a strict per-day loop inside the refresh command — download, parse, validate, and save one operating day, explicitly delete the parsed object and call `gc.collect()`, then move to the next day — so a single-day update and a thirty-day repair carry the identical, bounded memory footprint.
- The systemd timer moved from daily 09:00 to Monday-only 09:00 Sydney time, matching how often the numbers are actually reviewed and cutting unnecessary daily load on the server.
- Reanalysis weather data lags several days behind real time, so a Monday run couldn't assemble every leakage-safe input the price model needs without it and would silently publish a truncated forecast horizon. Recent *archived* weather forecasts are now ingested alongside observed and forward weather to close that gap.
- The later production-verified `v2.8.3` deployment contained the `v2.8.1` refresh changes. The first unattended Monday timer run remains a separate operating-event acceptance check rather than a claim made by this release note.

## 2.8.0: FlowTrace and ChargeTrace launch inside a unified NEM suite (11 August 2026)

- AEMO's gas and battery data had no dedicated product. FlowTrace (Gas Monitor) shipped, turning Gas Bulletin Board facilities, pipelines, effective-dated capacities, flows, storage, and adequacy forecasts into one physical-system view; capacity comparisons use the rating actually *in force* on the day shown, not today's rating, so a historical flow is never judged against a capacity upgrade that hadn't happened yet. ChargeTrace shipped alongside it, processing five-minute AEMO energy and FCAS dispatch for a declared battery asset registry into storage behaviour, cycle counts, an estimated observable market value, fleet-level comparison, and an opportunity-capture benchmark against a perfect-hindsight baseline — the product avoids the word "profit" throughout, since contracts, fees, losses, and private bids aren't observable in the public dispatch data it's built from.
- Fuel mix, the Price Predictor Lab, ChargeTrace, and FlowTrace were four separately-routed products. Navigation unified them under one shared `/nem/` prefix; every old top-level route became a permanent redirect instead of a dead link.
- Fuel, price, battery, and gas data each had a separately-triggered refresh job. One orchestration command now refreshes all four on the same schedule.
- `docs/DESIGN.md` and `docs/DEPLOYMENT.md` created as the site's master design and deployment references.
- `SITE_VERSION` moved off `2.7.3` for the first time since 27 June — the fifteen versions below cover the six weeks of work that shipped in the meantime without a version number attached to any of it at the time.
- Production verification covered routes, migrations, source loads, and a manual unified refresh. The first unattended timer-triggered refresh was explicitly left pending, so the release does not claim evidence that had not yet occurred.

## 2.7.15 — Price Predictor Lab ships — 6 August 2026

A new project: leakage-safe weekly NEM price forecasting built around a six-model ladder, from a no-fit "same as last week" baseline up to a neural network, where each model has to beat the one before it to justify the extra complexity it costs. Life Compass and the project that became World Ledger both received visual redesign passes the same day.

## 2.7.14 — StillPoint: control markup and hero CSS; Portfolio Pulse: three scoring models — 4 August 2026

- The ring (visual focus of the page) and the Begin control (the actual click target) were two separate elements — a `<div class="stillpoint__ring" id="sp-ring">` above a separate `<button class="btn btn-primary" id="sp-begin">`. In `stillpoint/templates/stillpoint/timer.html`, the ring became `<button type="button" class="stillpoint__ring" id="sp-ring" aria-label="Begin meditation">`; the `<div class="stillpoint__controls">` block (Begin + Reset buttons) was removed; "Begin" now renders as `<span class="stillpoint__pill" id="sp-begin">` inside the ring's own `.stillpoint__readout`. `#sp-phase` status text gained a `hidden` attribute, since the pill now carries that signal — one element to look at, one element to press.
- Vertical spacing in `static/css/stillpoint.css` used ad hoc rem values scattered through the file, per the diff's own comment. Added a spacing scale — `--sp-space-2xs` (0.35rem) through `--sp-space-3xl` (5rem) — and replaced the file's literal values with it. In the same pass: `.journal-eyebrow` set to `1.05rem`/`700` weight; `.stillpoint__hero h1` reduced from `clamp(1.9rem, 4vw, 2.6rem)` to `clamp(1.4rem, 3vw, 1.9rem)`/`400` weight/secondary colour; `.stillpoint__intro` paragraph and its rule block deleted.
- The "How to meditate" disclosure's expand affordance was hover-only — "invisible until you already know to look," per the diff's comment. Added `.stillpoint__guide summary::before { content: '+'; }`, a permanent marker.

Portfolio Pulse: three selectable health-scoring models added — **Plain Pulse** (fixed-weight deduction/addition formula, hand-calculable), **Signal Compass** (adds segment-aware continuous penalties and multiplicative context adjustments), **Retention Horizon** (Signal Compass plus a trend term, extended further in 2.8.3). All three read the same account data; switching models changes only the scoring function applied.

## 2.7.13 — Portfolio Pulse redesigned around three decision views — 30 July 2026

The original graph-accumulation MVP replaced with three purpose-built views — Portfolio Outlook, Customer Action Centre, Revenue Story — and the product standardized on ARR as its single revenue language, dropping the NRR/GRR/MRR mix the MVP had used.

## 2.7.12 — StillPoint: timer.js completion fix, feature trims, rename — 30 July 2026

- Master-mode completion was detected inside `tick()`, called only via `requestAnimationFrame`; browsers throttle or suspend `requestAnimationFrame` once a tab is hidden or a phone screen locks, so `tick()` could stop being called before `remaining <= 0` was ever checked, and a session that finished in the background never triggered `finish()` — no chime, no display update, indefinitely. Fixed in `stillpoint/static/stillpoint/js/timer.js` with `scheduleCompletionCheck()` — a `setTimeout` keyed directly to the existing wall-clock `endAt` value (`Date.now() + remaining * 1000`, unchanged since the MVP), independent of the rAF loop — plus a `visibilitychange` listener that recomputes `remaining` and calls `finish()` immediately if the tab regains focus after the session should already have ended. Student mode (`<audio>`-driven) needed no equivalent fix, since `<audio>` playback and its events run regardless of tab visibility.
- Same file: added feature-detected `navigator.wakeLock.request()` with reacquisition on `visibilitychange`; session history persisted to `localStorage` only, no server round-trip.
- A configurable interval-bell settings panel and numeric streak/minute-total counters had accumulated on the interface, reading as habit-tracker chrome rather than the "quiet place to sit" the product was meant to be. The settings panel was removed for one hardcoded two-minute cadence with no UI; counters were replaced with a 3-element recent-day dot row; the product was renamed "Meditation Timer" → "StillPoint" across templates, `apps.py`, and the admin-facing model description.

## 2.7.11 — Life Compass execution overhaul — 30 July 2026

A Projects/Daily-Tasks ledger toggle, kanban card aging with an archive, a redesigned X Calendar, and a Pomodoro focus overlay all landed in one pass. The browser's native `confirm()` prompt was replaced with a styled in-app dialog, and undoing a completed daily task now cascades to reopen its parent project if that's what the task belonged to.

## 2.7.10 — article image crop fix — 17 July 2026

Article images had a fixed 440px crop that was cutting off chart titles, axes, and legends — exactly the part of an image an article about data is most likely to need. Removed in favor of natural aspect ratio.

## 2.7.9 — Life Compass visual identity, dependency cleanup, silent contact-form bug — 14 July 2026

Life Compass adopted its parchment/brass/cartouche visual language with a compass-rose brand mark and self-hosted Playfair Display. Separately, `requirements.txt` was trimmed from 69 packages to 15 by tracing the actual import graph and removing an orphaned Wagtail stack and a leftover Jupyter/nbconvert stack that nothing in the codebase still used. Separately again: the contact form was found reporting success while silently sending nothing, because an unset `CONTACT_EMAIL` environment variable produced an empty recipient list, and Django's `EmailMessage.send()` returns `0` rather than raising an exception on an empty list. Fixed by treating a zero-send result and a missing recipient as explicit, surfaced failures rather than a quiet no-op.

## 2.7.8 — Life Compass execution workflow, phases 1–3 — 13 July 2026

Daily tasks changed from freeform text entries to selections pulled directly from a project's open subtasks. Calendar completion marks became earned automatically from real task completion instead of manually toggled by the user. Duplicate "complete" controls removed, and a defensive dedup guard added to the Done Ledger after it was found capable of double-counting the same completion.

## 2.7.7 — Life Compass goes private — 8 July 2026

Session-based authentication added, backed by one JSON document per user synced to the browser's `localStorage`. Fixed a 404 on the public demo's strategy data and a header-overlap layout bug; login/logout moved into a dedicated Settings panel.

## 2.7.6 — Life Compass and Portfolio Pulse added — 7 July 2026

Two new projects added in one sitting, both filed under a new Commercial Intelligence category; homepage tool rotation added so the front page doesn't statically favor one product over the others.

## 2.7.5 — category taxonomy settled — 28–30 June 2026

Public categories cycled from an initial four-way split (including a short-lived "Society & Policy") to the taxonomy still in use today: **Energy Systems · Data Stories · Human Performance · Commercial Intelligence**. About-page and Contact/Projects positioning copy revised to match.

## 2.7.4 — tagline, admin, and copy refinements — 27 June 2026

Tagline reworked around four interest areas with title-case headings; project categories made visible, editable, and filterable in Django admin; homepage typewriter topics aligned to the new taxonomy; duplicate footer links removed.

## 2.7.3 — SITE_VERSION rendered in production — 27 June 2026

The `SITE_VERSION` constant — the same one every version number in this document traces back to — started rendering on the live site. Obsolete root-level deployment and planning documents removed from the public repository.

## 2.7.2 — CSS split into source partials — 27 June 2026

One monolithic stylesheet split into tokens, base, and per-area partials (home, blog, about, NEM, projects, StillPoint, marginalia) — same visual cascade, organized source. `django-compressor` added so production still serves one cached, minified stylesheet while development serves the readable partials directly; a custom filter preserves relative asset URLs (like the fleur-de-lys mask image) through the bundling step. Private redesign reports and security-audit material stopped being tracked in the public repository.

## 2.7.1 — footer links, fleur-de-lys mask, mobile nav fix — 27 June 2026

Footer quick links and a tagline added. The fleur-de-lys motif enlarged and given a theme-aware terracotta color mask to match the kolam motif used elsewhere. Fixed the mobile hamburger and theme toggle drifting into the expanded menu by anchoring both to the top row.

## 2.7.0 — contact reliability, production security, search metadata — 26 June 2026

Contact delivery rebuilt around `EmailMessage` with a proper Reply-To header, a honeypot field, rate limiting, and failures that surface instead of failing silently. Production security hardened with environment-gated SSL redirect, HSTS, and standard security headers. `sitemap.xml`, `robots.txt`, per-page titles and descriptions, canonical/viewport metadata, WebSite/Person/Article JSON-LD, and Open Graph tags added. NEM CSV imports gained validation and import summaries; guided-audio uploads restricted to validated MP3 files. A 16-test regression suite added, and two dangerous legacy management commands removed from a production-reachable state. This is the commit where `SITE_VERSION` first existed in code.

## 2.6.0 — StillPoint ships; NEM fuel-mix query bug fixed — 25 June 2026

- New Django app `stillpoint/`. `models.py`: one `GuidedMeditation` model — `title` (CharField), `description` (CharField, blank), `audio` (FileField), `order` (PositiveIntegerField, default ordering). `templates/stillpoint/timer.html` + `static/stillpoint/js/timer.js` (218 lines). Master mode: SVG ring, `r=110` circle, `stroke-dashoffset` set from `remaining / durationSec` each animation frame. Chime: two `OscillatorNode`s at 432Hz and 648Hz, `GainNode` ramped 0→peak over 20ms and peak→0 over 3.5s (peaks 0.35 and 0.12) — no audio file dependency. Guide Me mode plays the admin-uploaded `GuidedMeditation.audio` file through the same ring markup, in place of the synthesized chime. No streak field, no user model, no settings template in this version.
- The original NEM dashboard query — `FuelGenerationData.objects.all().values('fuel_type').annotate(total_gen=Sum('supply_mw'))` — summed *every row the database had ever stored* with no date filter at all, defaulting to NSW, since `1.4.0`. That headline number was replaced with an explicitly dated 7-day generation window plus a separate 3-month renewables-vs-fossil trend, with AEST time handling and AM/PM CSV parsing fixed alongside it.
- Marginalia added site-wide: a terracotta brick ribbon, a line-drawing watermark, footer symbols, a randomly positioned favicon page mark.
- Blog changed to a randomly-selected featured introduction with a restyled pager and larger thumbnails; About rewritten with numbered interest blocks.
- (The version number jumps straight from `2.0.0` to `2.6.0` here — the author's own label, one day after the redesign below, covering a new project and a dashboard reframe that would ordinarily have earned several separate minor releases.)

## 2.0.0 — the Austro-Indo-French redesign — 24 June 2026

The single commit that changed the site's look more than any other. Before: Bootstrap's stock defaults — primary blue `#0d6efd`, off-white `#f8f9fa`, dark-grey-on-charcoal dark mode `#212529` — the same palette every unstyled Bootstrap site ships with. After: warm linen `#f4f0e6`, forest ink `#1a2e1a`, forest green `#2d6a2d`, terracotta `#b84a1a`, with a parallel dark theme (deep forest night `#141910`, warm cream `#f0ede0`), Playfair Display serif headings, and CSS custom properties throughout so both themes stay driven by one token set. The stylesheet grew roughly fivefold in this one commit. Blog redesigned, an about page added, a typewriter text effect introduced on the homepage, footer rebuilt, article layout reworked. The article-package publishing pipeline (source Markdown + metadata + figures, imported by slug) set up, with the first batch of articles published through it.

*Nine and a half months separate this release from the one before it (`1.4.2`, 6 August 2025) — no commits exist in that window. Whatever happened to the site between those two dates, if anything, left no trace in git history.*

## 1.4.0 – 1.4.2 — the first NEM dashboard — 4–6 August 2025

The site's first interactive data product: a Chart.js bar chart, one canvas element, colored by a hardcoded list of ten fuel types with an emoji icon apiece (⬛ black coal, 💨 wind, 🔆 solar, and so on). The view queried the whole `FuelGenerationData` table with no date bound whatsoever and defaulted to NSW — the bug that stood for almost a year until `2.6.0` fixed it. The shipped commit still contained an earlier, abandoned attempt at the same dashboard alongside the working one (`old_views.py`, `old_chart_code.js`), and the working version's own JavaScript was left with debug `console.log` calls and emoji warning markers in production. Two small follow-ups closed out the version: an unnecessary image removed, and a stray Windows-only `pywin` entry cleaned out of `requirements.txt` (it had no purpose on the Linux production host it was never going to run on).

## 1.3.0 – 1.3.1 — Markdown rendering, multi-image articles — 26–28 July 2025

Markdown rendering added for article bodies; support added for multiple images per article. Follow-up fixes: images not displaying correctly on some blog posts, dark-mode bugs. A background-toggle option was tried and deliberately not shipped.

## 1.2.0 – 1.2.1 — first presentation overhaul — 10–11 June 2025

Site structure and look-and-feel revamped; blog view changed to a card-style layout. Groundwork laid for importing notebooks from a local machine into published content. Follow-up: a broken LinkedIn link fixed.

## 1.1.1 – 1.1.3 — making the app deployable — 17 April – 2 May 2025

A `seed_data` command added so a fresh install could be populated with sample projects and posts. `SECRET_KEY`, `DEBUG`, and `ALLOWED_HOSTS` moved out of hardcoded settings into environment variables, with a follow-up fix to the `SECRET_KEY` assignment itself; static/media settings reorganized and `STATIC_ROOT` corrected for production. Wagtail — installed at project start and never actually used — removed from `requirements.txt`; Willow downgraded to 1.5.0.

## 1.1.0 — blog, contact form, dark mode added — 16 April 2025

Blog and project Django models, migrations, and templates added. A working contact form added, with its own success page. Full dark mode added, including icon treatment.

## 1.0.0 — initial Django scaffold — 11 April 2025

Django scaffolded from scratch, after an earlier attempt was deliberately wiped ("start fresh, let's build it for real now"). The entire homepage template at this point was:

```html
<h1>Welcome to the Portfolio</h1>
<p>This is the beginning of something great.</p>
```

No CSS, no models, no routes beyond the one page. Django installed (Wagtail was installed here too, then removed in `1.1.3`); `requirements.txt` and `.gitignore` created. Nothing before this commit exists in the repository.

---

## How game studios and business software track this, and which one this project should follow

Two established traditions exist for writing down "what changed," and they optimize for opposite readers.

**Live-service game patch notes** — Age of Empires II: Definitive Edition is a good example — are written for players who will test the exact numbers against their own experience within the hour. A civilization bonus that moves from +2 to +3 villager HP is stated as exactly that, because an audience of thousands who play the matchup daily will notice a vague "improved balance" as evasive, or worse, as something being hidden. Alongside the numeric changelog sits a separate "designer notes" voice explaining *why* — what data showed a unit was underused, what the intended new role is — commentary and numbers side by side, neither one replacing the other. The audience is expert, skeptical, and numerous enough that imprecision gets caught immediately, so precision is what earns trust.

**Business and enterprise software** release notes are written for the opposite reader: someone who is often non-technical, reading to answer "does this affect me" rather than "how does it work," and who vastly outnumbers anyone capable of evaluating an implementation detail. So they compress — "improved dashboard performance" stands in for whatever engineering actually happened — and semantic versioning communicates compatibility risk more than content. The real engineering detail, if it's written down at all, lives in a separate internal changelog nobody outside the team reads, because customer-facing and engineering-facing are treated as two different documents for two different audiences.

This project doesn't have that audience split, which is the whole reason the AoE2 model fits it better than the enterprise one. There's no customer base deciding whether to upgrade; the reader is either the author months from now, or someone evaluating whether the engineering claimed here actually happened and was reasoned through — closer to the expert, skeptical AoE2 player than to an enterprise admin skimming for a compatibility warning. Hiding the mechanism behind "improved reliability," the way business software does for a mass non-technical audience, would defeat the one thing this document is for.

Concretely, going forward:

1. **Write the entry at release time, from the diff, not months later from a commit message.** The gap between `2.7.3` and `2.8.0` — six weeks, four new projects, no version number attached to any of it at the time — is what specificity loss actually looks like in this project's own history. It was recoverable this time because the file diffs still existed; it won't always be.
2. **Assign a version to every deployed change immediately**, the AoE2/business-software discipline both share even where they differ on tone. `docs/DESIGN.md`'s release checklist now includes writing the release-notes entry as its own step; a git hook that refuses a commit changing `SITE_VERSION` without a matching `docs/RELEASE_NOTES.md` change would make that structurally hard to skip rather than a habit that can lapse.
3. **State the number, not the adjective.** "Sums the entire table with no date filter" is worth more than "was inaccurate." "Gain 0.5 vs. 0.9" is worth more than "quieter." A reader who wants adjectives can get those from the site itself.
4. **Keep the reasoning attached to the number**, the way a designer note sits next to a balance change. The k-means fit for Portfolio Pulse excludes health score from its inputs for a specific reason — so the clustering reflects behaviour instead of restating a number computed elsewhere — and that reason is exactly the part a portfolio needs to demonstrate, not the clustering algorithm's name by itself.
