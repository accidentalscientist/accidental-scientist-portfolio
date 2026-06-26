# Accidental Scientist — Redesign & Engineering Report

**Project:** accidentalscientist.net — personal portfolio of Thibault Aymonier-Newman
**Scope of this report:** the full redesign and feature build carried out across this engagement (site versions **v1.4.1 → v2.6.0**)
**Author:** Engineering pair-session report
**Date:** June 2026

---

## Table of contents

1. Executive summary
2. Part I — The site as it was before
3. Part II — The changes we made (and why)
4. Part III — Design review: current and future state
5. Part IV — Security audit
6. Appendix A — Version history
7. Appendix B — Deployment runbook
8. Appendix C — File & component inventory

---

## 1. Executive summary

This engagement took a functional but visually plain Django portfolio — two blog posts, a single energy dashboard, default Bootstrap styling — and rebuilt it into a coherent, editorially-designed product aimed at green-energy-transition employers.

The work fell into three streams, all of which were completed and deployed to the live DigitalOcean droplet:

1. **Blog / content** — an editorial redesign of how writing is presented, a structured content pipeline (a separate "articles" repository imported by a management command), and **11 long-form articles** published.
2. **NEM Dashboard** — a substantial rework of the National Electricity Market fuel-mix tool: a true point-in-time / last-7-days breakdown, a new three-month renewables-vs-fossil-fuels trend chart, correct Australian timezone handling, and a robust CSV ingestion path.
3. **Stillpoint** — a brand-new Django app: a minimalist meditation timer with a silent "Master" mode and an audio-guided "Guide me" mode.

Alongside these, the entire visual identity was rebuilt: a bespoke "austro-indo-french" design system (warm linen, forest ink, terracotta; Playfair Display headings), a full light/dark theme, and a set of subtle decorative "marginalia" (a brick edge ribbon, a coastal-abbey watermark, and footer flourishes — a fleur-de-lys and a Tamil kolam/Om).

The codebase grew from two apps to three, gained a structured editorial workflow, and shed a meaningful amount of dead code. This report documents the prior state in detail, every significant change and the reasoning behind it, a forward-looking design review, and a security audit with prioritised recommendations.

---

## 2. Part I — The site as it was before

### 2.1 Purpose

The site is a personal portfolio and writing platform. Its goals are to (a) present Thibault as a credible candidate for roles in Australia's energy transition, data and analytics; (b) host long-form data-storytelling articles; and (c) showcase interactive data tools — chiefly the NEM fuel-mix dashboard.

### 2.2 Technology stack

| Layer | Technology |
|---|---|
| Framework | Django 5.2 (Python) |
| Database | PostgreSQL (via `psycopg2-binary`) |
| Front-end CSS | Bootstrap 5.3 (CDN) + a custom stylesheet |
| Charts | Chart.js (CDN) + `chartjs-plugin-datalabels` |
| Templating | Django templates (server-rendered) |
| Hosting | DigitalOcean droplet (Ubuntu 24.04), Gunicorn + systemd, behind a socket served by the web tier |
| Config | `python-decouple` / `python-dotenv` reading a gitignored `.env` |
| Email | Gmail SMTP (TLS) for the contact form |

The project is a classic server-rendered Django monolith — no SPA framework, no REST API layer for the front-end. JavaScript was used sparingly (a dark-mode toggle, a navbar shrink behaviour, and the Chart.js dashboard).

### 2.3 Application architecture (before)

Two Django apps under a `config` project:

- **`portfolio`** — the public site. Models: `Project` (title, slug, description, image, `project_url`, date) and `BlogPost`. Views for the home page, all-projects list, project detail, blog list, blog detail, and a contact form. Templates extended a single `base.html`.
- **`nem_dashboard`** — the energy tool. Models: `FuelGenerationData` (timestamp, state, fuel_type, supply_mw) and `FuelDataUpload` (a CSV `FileField`). A `post_save` signal parsed an uploaded CSV into `FuelGenerationData` rows. A single `dashboard` view aggregated the data and rendered a Chart.js page.

Cross-cutting pieces: `markdownx` (added during this engagement for live markdown editing in the admin), custom context processors injecting `now` and global site info (site name, tagline, GitHub/social URLs), and a `sitemaps` app.

### 2.4 State of the code (baseline assessment)

**Strengths**
- Clean separation of concerns between the two apps.
- Secrets correctly externalised to environment variables (`SECRET_KEY`, DB credentials, email, `DEBUG`, `ALLOWED_HOSTS`).
- Sensible use of Django's ORM and the admin.

**Weaknesses we found**
- **Visual identity was generic** — default Bootstrap look, an aborted "aurora gradient" experiment leaving a muddy background, and inconsistent surfaces (white navbar fighting CSS variables).
- **The NEM dashboard was conceptually muddy** — it summed `supply_mw` across *every* timestamp in the database rather than showing a point-in-time mix, defaulted to NSW instead of the whole market, used bright "2000s" fuel colours, and mixed a Chart.js canvas with a separate hand-rolled HTML bar list.
- **Dead code** — `old_views.py`, `old_chart_code.js`, and an unused `fuel_extras` templatetag.
- **Timezone** was UTC despite being an Australian-only product, so timestamps read confusingly.
- **The blog had only two posts** and the `BlogPost` content was a plain `TextField` with thin presentation.
- **The contact form** had a latent bug (see the security audit) and no spam protection despite `django-recaptcha` being installed.

---

## 3. Part II — The changes we made (and why)

This is the core of the report. Changes are grouped by area. Throughout, a visible version tag in the top-left corner (`vX.Y.Z`) was incremented on every change so the live state could be confirmed after each deploy — a deliberate feedback mechanism given browser-cache friction.

### 3.0 Working method

We worked in tight iterations: make a change locally, bump the version tag, verify by rendering pages through Django's test client and a system check, then surface the result for review. For genuinely subjective design decisions (the editorial card layout, the marginalia) we produced visual mock-ups before committing code, to avoid building the wrong thing.

### 3.1 The design system (`static/css/style.css`)

The single largest artefact is the stylesheet, effectively rewritten into a coherent **"austro-indo-french" design system**. The intent: *Austrian* precision (a strict grid, square-edged "stamp" elements, restrained geometry), *Indian* warmth (linen surfaces, a terracotta accent, ornament), and *French* editorial polish (Playfair Display italic headings, wide-tracked uppercase labels, generous line-height).

Key foundations, expressed as CSS custom properties:

- **Light palette:** `--bg-primary` warm linen `#f4f0e6`; navbar slightly lighter, footer slightly darker (a deliberate three-surface gradient from header → body → footer); `--text-primary` forest ink `#1a2e1a`; `--text-secondary` sage; `--accent-color` forest green `#2d6a2d`; `--accent-warm` terracotta `#b84a1a`.
- **Dark palette:** a full parallel set (`[data-theme='dark']`) — deep forest night, cream text, muted sage — so every component works in both modes.
- A late addition, **`--page-width: 1140px`**, was introduced as a single knob controlling the content width across every main page (see §3.12).

**Why:** the previous look undercut the content's credibility. A distinctive, restrained, editorial identity signals design literacy to the energy/data audience without being loud. Using CSS variables (rather than hard-coded colours) made the light/dark theming and later tuning trivial.

Notable component work in the stylesheet: square-edged category "stamps"; a terracotta-striped "key takeaway" block; the editorial featured-article card; the project list-rows; the NEM dashboard components; the Stillpoint timer; the marginalia; and a blended editorial pager. Several bugs were fixed along the way (a stray `</style>` tag, the undefined `auroraShift` keyframes, Bootstrap's `bg-light` overriding the navbar variable, and duplicated rules).

### 3.2 Base template, navigation and theming (`base.html`)

- Added Google Fonts (Playfair Display + Inter, later Noto Sans Tamil for the Om glyph).
- Removed Bootstrap's hard-coded `navbar-light bg-light` classes that were fighting the CSS variables; the navbar now uses `--bg-navbar` with a subtle double-rule bottom border.
- Centred brand, right-aligned dark-mode toggle, centred nav links.
- Added `{% block extra_css %}` / `{% block extra_js %}` hooks.
- Added the persistent version tag and, later, the marginalia elements and the random-placement favicon "page-mark" script.

**Why:** establish a single, theme-aware shell that every page inherits, and create extension points for page-specific assets.

### 3.3 Homepage (`home.html`)

- Replaced the static eyebrow with a **typewriter effect** cycling through themes (Data Science, Energy Systems, Football Analytics, Grid Transition, Climate Policy, NEM Data, Human Performance, Renewable Energy). The speed constants were later surfaced as named, commented variables so they're trivially tunable.
- Reworked the hero copy to be broader and renewables-focused, with a more poetic heading ("Energy, systems, and human performance.") and a reduced height.
- Made the **"Current project" card dynamic** — it now shows whichever `Project` is most recent (previously the NEM dashboard was hard-coded).
- **Featured writing** went through several iterations: from a list, to an editorial "lead + secondary" layout, finally to a **single random featured article presented as an intro** (no large image — a text-forward card with category, Playfair title, a ~55-word intro, and meta). The randomisation means the homepage feels fresh on each visit.
- Added the faint **coastal-abbey watermark** behind the hero (see §3.10).

**Why:** the homepage is the first credibility signal. Hierarchy ("read this first"), motion (the typewriter), and a living "current project" make it feel active and intentional rather than a static brochure.

### 3.4 The blog system

This was Action Item 1 and the most content-heavy stream.

**Model & admin (`portfolio/models.py`, `admin.py`).** `BlogPost` gained editorial fields: a `Status` (draft/published) with a published default, a `Category` enum, a `MarkdownxField` for `content` (replacing the plain `TextField`, giving a live split-pane markdown editor in the admin), `key_takeaway`, `updated_at`, `is_featured`, and an `external_url`. A `reading_time_minutes` property (word count / 200) was added. The admin uses `MarkdownxModelAdmin` with grouped fieldsets.

**Categories.** Finalised as **Energy transition, Data Stories, Society & policy, Human performance**. "Other" was removed (no posts used it) and "Sport & performance" was renamed to "Human performance" so football/running analytics have a clear home. These are `TextChoices`; changing them generated migrations `0010`/`0011` (label/choice changes only, no data migration — the underlying `sport` value was preserved).

**Views (`views.py`).** `blog_list` filters by category via a GET param and surfaces a single random featured post; `blog_detail` renders markdown via `markdown2` (with a configured extras list) and performs an `[[image1]]`/`[[image2]]` placeholder substitution, replacing tokens with `<figure>` blocks built from `BlogImage` records.

**Templates.** The blog list got a journal hero, square category-filter pills, a featured section, and a thumbnailed "all writing" list (thumbnails later enlarged from 112×84 to 152×114). The detail page got a "Back to Writing" link, a category eyebrow, a widened reading column (760 → 960px), and the terracotta key-takeaway block. The Bootstrap pagination was replaced with a **blended editorial pager** (uppercase forest links, a Playfair "Page X of Y", terracotta hover, faded-disabled states).

**Content pipeline — the articles repository.** Rather than authoring inside the website DB, articles live in a **separate Git repository** (`elite-analytics-articles-2026`). Each article is a folder containing `article.md`, a `metadata.json` (title, slug, category, summary, key_takeaway, cover_image, inline_figures, source_notebooks), and a `figures/` directory. A management command, **`import_elite_articles --publish`**, walks `articles/`, and for each package runs `update_or_create` keyed on slug (so it is idempotent — re-running updates existing posts and adds new ones, never duplicating), attaches the cover image and inline figures, and sets status. `ELITE_ARTICLES_DIR` is a configurable setting defaulting to a sibling directory.

**Why this architecture:** it cleanly separates *editorial source* (notebooks, figures, prose, version-controlled) from the *website*, lets articles be drafted and reviewed independently, and makes publishing a single reproducible command. A real-world debugging session confirmed its value — cover images initially imported as `None` because nine article packages had been committed locally but **not pushed**; the importer silently skips an absent `cover_image`, so the fix was simply to push the articles repo, not to touch code.

By the end, **11 articles** were live (Australia's grid transition, power-system mapping, energy balance, the global green transition, climate evidence, climate risk & policy, the weekly energy fingerprint, world development, the Premier League, city inequality, and a personal Parkrun analysis).

### 3.5 About page (`contact.html`)

Rebuilt from a bare contact form into a proper About page:

- A bio hero — the personal name was later removed in favour of a positioning statement ("On data, systems, and human performance.") leading with "experienced commercial manager and a lifelong lover of data".
- A 2×2 **interests grid** — Energy transition, Data science, Human performance (football/running analytics, adaptation to stress, behaviour change & habit formation), and Society & policy. Emoji markers were replaced with elegant **terracotta Playfair numerals (01–04)** because the emoji "looked a little AI".
- A contact section retitled to a single "Get in touch" heading, with the form inputs restyled to match the site (linen surface, soft borders, rounded corners, uppercase labels, a forest-green focus ring) instead of the default blocky Bootstrap inputs.

### 3.6 Projects page (`projects.html`)

Iterated from a basic Bootstrap card grid → a feature-launcher experiment (reverted at the user's request) → the final **interactive list-row pattern**: each project is a substantial padded card-row with a large Playfair title, a "Live tool" badge, a one-line description, and an arrow that nudges on hover. This pattern scales gracefully from one project to many — it never shows the awkward "single card in a grid" problem.

### 3.7 NEM Dashboard (Action Item 2 + later rework)

The most substantial engineering. Two phases.

**Phase 1 — point-in-time correctness and a modern look.**
- **Defaults to NEM** (the whole market), not NSW.
- Computes a **true point-in-time snapshot** (the latest timestamp per region) rather than summing across all history.
- Pre-builds data for *all* regions server-side and embeds it, so the **region auto-cycle** (and manual selection) happens instantly client-side with no page reloads.
- Replaced the Chart.js/HTML-bar mix with **clean animated CSS bars** plus stat cards and a renewable-vs-fossil split, in refined muted fuel colours that match the palette.
- Reframed honestly as a "point-in-time snapshot" with the snapshot date surfaced.
- **Battery reclassified as storage**, not renewable (it discharges stored energy), and shown as its own category so it isn't hidden.
- **CSV ingestion** kept admin-only (a brief public upload endpoint was added then removed at the user's request — data updates should be the owner's alone), with the parser made idempotent (re-uploading a snapshot replaces it rather than double-counting).

**Phase 2 — the 7-day / 3-month rework.**
- The headline breakdown now **sums the most recent 7 days** of data, with explicit "Last 7 days" labelling throughout.
- Added a **3-month trend chart** (Chart.js line) showing **renewables vs fossil fuels** as two competing lines — later made bold (vivid green vs vivid red, thick strokes, translucent fills) "to see the fight" — for every region including the NEM aggregate, explicitly labelled "Last 3 months" and noting battery is excluded.
- Headline stats settled as four boxes: **Total generated (MWh, 7 days) · Renewables · Coal · Gas**.
- Fuel emojis were refreshed to be more characterful (🪨 coal, ⛏️ brown coal, 🔥 gas, 🛢️ liquid, 🌊 hydro, 🌬️ wind, ☀️ solar, 🔋 battery, 🌿 biomass).
- Title capitalised to **"National Electricity Market — Fuel Mix Generation"** with a fuller explanatory intro.

**Supporting bug fixes** (see §3.13): timezone, am/pm CSV parsing, and a hard-coded localhost project URL.

**Why:** the original tool was technically misleading (summing all history) and visually dated. The redesign makes the *what* explicit (a 7-day mix), adds genuine analytical narrative (the 3-month renewables-vs-fossil contest), and treats storage vs generation honestly — the kind of domain nuance that signals real understanding to an energy employer.

### 3.8 Stillpoint — a new app (Action Item 3)

A brand-new Django app built from scratch: a minimalist meditation timer.

- **Model:** `GuidedMeditation` (title, description, audio `FileField`, order) — managed entirely through the Django admin.
- **View / URL / template:** a single timer page at `/stillpoint/`.
- **Master mode** — a silent self-guided timer with presets **2 / 5 / 9 / 15 / 30 / 60** minutes (default 15), Begin/Pause/Resume/Reset.
- **Guide me mode** — plays an admin-uploaded audio track; the ring and countdown follow the audio.
- A large Playfair countdown inside a depleting SVG progress ring, with a slow "breathing" animation while running, and a **soft synthesized start/end bell** generated via the Web Audio API (no audio file required, so Master mode works immediately).
- A **stoic, minimalist** aesthetic in the site palette.

It was added as a `Project` row so it appears on the Projects page with a "Live tool" badge. A late fix prevented the guided audio's metadata from clobbering the Master-mode default to the track's length (the "shows 9:00" bug), and the two modes were given equal min-height so switching doesn't shift the layout.

### 3.9 The footer (`footer.html`)

Rebuilt with a Playfair italic brand, corrected LinkedIn URL, and a compact layout; later slimmed further (the ornamental diamond and tagline removed) to reduce height. It became the anchor for two pieces of marginalia (§3.10).

### 3.10 The marginalia — a decorative identity system

A deliberate set of faint, non-interactive, edge-placed ornaments expressing the three cultural strands, all `aria-hidden`, low-opacity, and responsive (hidden on smaller viewports):

- **Terracotta brick ribbon** down the left edge (running-bond pattern) — the boldest gesture, framing every page.
- **Coastal-abbey watermark** (Mont-Saint-Michel → ultimately the user's own `coastal_castle.svg`, white background stripped, tinted terracotta) as a faint backdrop behind the home hero.
- **Footer flourishes** — a **fleur-de-lys** (French; the user's PNG, dropped onto the linen via `mix-blend-mode`) bottom-left, and a **kolam + Tamil Om (ௐ)** (Indian) bottom-right, bookending the footer.
- A **favicon "page-mark"** that lands in a **random one of 12 positions on each page load**, with a tilt that is straight ~50% of the time and otherwise slightly-to-wildly off.

**Why:** these give the site a memorable, personal signature tied to the three-culture concept, without compromising legibility — they whisper rather than shout.

### 3.11 Footer/marginalia overlap & responsive hygiene

On small screens the dark-mode toggle could collide with the mobile hamburger; the hamburger was moved to the left on mobile. The favicon mark is now only shown when the viewport is wide enough (>1280px) to have real gutter space beside the centred content, eliminating overlap.

### 3.12 Unified page width

Each page had imposed its own max-width (Projects 880, NEM 900, About 760) while Home/Blog filled the Bootstrap container — so navigating between pages caused the content width to jump. A single **`--page-width`** variable applied to the main container, with per-page caps removed, now keeps every main page the same width (Stillpoint deliberately excepted as a centred timer), responsive below that width.

### 3.13 Bug fixes worth recording

- **Timezone:** `TIME_ZONE` changed UTC → `Australia/Sydney`; the CSV parser made timezone-aware (no more naive-datetime warnings).
- **CSV date formats:** the parser now accepts both 24-hour (`28/07/2025 17:55`) and 12-hour am/pm (`25/06/2026 10:10 am`) — a real failure where a re-upload silently imported zero rows.
- **Hard-coded localhost:** a `Project.project_url` of `http://127.0.0.1:8000/nem/` would have broken on production; normalised.
- **Stillpoint 9:00 bug:** guided audio metadata was overriding the Master default; guarded to guided mode only.
- **Dead code removed:** `old_views.py`, `old_chart_code.js`, `fuel_extras.py`.

### 3.14 Deployment & infrastructure

The live project runs from `/home/thibault/accidental-scientist-portfolio`, served by Gunicorn as user `thibault`. The standard deploy is: push to GitHub → on the server `git pull` → `pip install -r requirements.txt` → `migrate` → `collectstatic` → restart Gunicorn; articles deploy by pulling the articles repo and re-running the import. We codified this and recorded two recurring gotchas: a `collectstatic` permission error (some `staticfiles` were root-owned and need `chown -R thibault:www-data`), and the fact that **DB/media data does not travel through git** — `Project` rows, the `GuidedMeditation` audio, and NEM CSVs must be (re)created on the server. `django-markdownx` was also added to `requirements.txt` (it had been installed but unpinned).

---

## 4. Part III — Design review: current and future state

### 4.1 Current state — assessment

**Strengths**
- A genuinely distinctive, coherent visual identity that is rare in developer portfolios.
- Strong content hierarchy (editorial featured article, journal blog, list-row projects).
- The NEM dashboard now tells an honest, layered story (7-day mix + 3-month contest) with domain-correct classifications.
- Clean light/dark theming and a maintainable, variable-driven stylesheet.
- A reproducible content pipeline and a documented deploy.

**Risks / rough edges**
- The contact form has a functional bug (Part IV) — the primary call-to-action may be failing silently.
- The 46 MB meditation **WAV** is a heavy asset for web delivery.
- The single large `style.css` is approaching the size where it would benefit from being split into partials or a small build step.
- A visible dev **version tag** still ships on production.
- The dashboard's "Total generated" figure is daily-energy (MWh) summed over 7 days — correct, but worth a tooltip clarifying units for lay readers.

### 4.2 Future opportunities

- **Content & SEO:** per-article Open Graph images, structured data (JSON-LD `Article`), an RSS feed, and a `/now` page. The sitemaps app is already installed and could be fully wired.
- **NEM dashboard:** an optional gas-as-third-line view; emissions-intensity overlay; auto-refreshing data via a scheduled AEMO fetch instead of manual CSV upload; a small "as at" data-freshness banner.
- **Stillpoint:** interval bells for longer sits; an ambient soundscape option; saving a session streak in `localStorage`; converting audio to streaming-friendly MP3/AAC.
- **Performance:** image `srcset`/lazy-loading audit, CSS minification, Subresource Integrity (SRI) on CDN assets, and self-hosting fonts to remove third-party requests.
- **Accessibility:** a full audit (focus order, colour-contrast in dark mode, reduced-motion handling for the typewriter and breathing animations).
- **Engineering:** a test suite (there is currently minimal coverage); CI to run `manage.py check` and tests on push; optionally a small CI/CD deploy hook to replace the manual server steps.

### 4.3 Open decisions for the owner

1. **Data freshness for the NEM dashboard** — keep manual CSV uploads, or invest in an automated AEMO ingestion? This is the single biggest "is this live data?" credibility question.
2. **Audio strategy for Stillpoint** — host one's own tracks (storage/bandwidth cost) or embed/stream? And whether to expand the guided library.
3. **Gas presentation** — keep gas inside the fossil line in the 3-month chart (current) or promote it to a third line (renewables vs coal vs gas).
4. **CSS tooling** — stay with a single hand-written stylesheet, or adopt a light build (partials + minification)?
5. **Domain/branding permanence** — the NEM project URL is stored absolute (`http://accidentalscientist.net/nem/`); a relative URL would be more portable if the domain ever changes.

---

## 5. Part IV — Security audit

**Scope:** application-level review of the Django codebase and configuration, plus infrastructure observations from the deployment sessions. This is a code-and-config review, not a penetration test. Severity is rated by realistic impact for a low-traffic personal site.

### 5.1 Summary of findings

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | Contact view passes unsupported `reply_to=` to `send_mail()` | High (functional) | Open |
| 2 | No spam/abuse protection on the contact form (`django-recaptcha` installed but unused) | Medium | Open |
| 3 | Missing production HTTPS/security headers (HSTS, secure cookies, SSL redirect, nosniff) | Medium | Open |
| 4 | SSH password authentication / root login appears enabled on the droplet | Medium | Observed |
| 5 | Markdown rendered without sanitisation (`markdown2`, no safe mode) | Low (admin-authored) | Accepted-ish |
| 6 | Inline-figure/caption HTML built by string interpolation | Low (admin-authored) | Note |
| 7 | CDN assets loaded without Subresource Integrity | Low | Open |
| 8 | Dev version tag and framework details exposed in production HTML | Informational | Open |

### 5.2 Detailed findings

**1 — Contact `send_mail(reply_to=...)` (High, functional).** `portfolio/views.py:contact_view` calls `send_mail(..., reply_to=[email])`. Django's `send_mail()` does not accept a `reply_to` argument, so a valid submission raises `TypeError` and 500s — the contact form, the site's main call to action, is likely broken. **Fix:** build an `EmailMessage` (which does support `reply_to`) and call `.send()`, or simply drop the kwarg. While fixing, add server-side validation/length caps. *Security-adjacent:* user input flows into the email subject/body; Django blocks header injection via newlines (raising `BadHeaderError`), so the main injection risk is mitigated, but this should be confirmed once the send path is corrected.

**2 — No anti-spam on the contact form (Medium).** `django-recaptcha` is in `requirements.txt` but not in `INSTALLED_APPS` and not wired into `ContactForm`. A public POST endpoint that sends email is a spam/abuse vector. **Fix:** enable reCAPTCHA (already a dependency) or add a honeypot + rate limit (e.g. `django-ratelimit`).

**3 — Production security headers (Medium).** `settings.py` sets none of the HTTPS-hardening options. Recommended for production (guarded by an env flag so local dev is unaffected): `SECURE_SSL_REDIRECT=True`, `SECURE_HSTS_SECONDS` (with includeSubDomains/preload once confident), `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`, `SECURE_CONTENT_TYPE_NOSNIFF=True`, and an explicit `X_FRAME_OPTIONS='DENY'` (the clickjacking middleware is present and defaults to SAMEORIGIN). Confirm TLS is terminated for `accidentalscientist.net` and that HTTP redirects to HTTPS. Run `python manage.py check --deploy` and resolve its warnings.

**4 — SSH hardening (Medium, infra).** During deploys the droplet accepted **password authentication for `root`**. Recommended: use SSH keys only, set `PermitRootLogin prohibit-password` (or create a non-root sudo user and disable root login), `PasswordAuthentication no`, and consider `fail2ban`. Keep the OS patched (the server reported pending updates and a required restart).

**5 — Markdown sanitisation (Low).** Blog content is rendered with `markdown2` without safe mode, so raw HTML in a post passes through. Content is authored only by the site owner via the admin, so the practical risk is low (it depends entirely on the admin account not being compromised — see #4). If guest authorship is ever added, switch to a sanitising renderer or post-process with `bleach` (already a transitive dependency).

**6 — Inline-figure HTML interpolation (Low).** `blog_detail` builds `<figure><img ... alt="{caption}">` via f-string interpolation of admin-supplied captions. Admin-authored, so low risk, but using Django's template/`format_html` escaping would be more robust.

**7 — CDN assets without SRI (Low).** Bootstrap, Chart.js and the icon fonts load from CDNs without `integrity`/`crossorigin`. A CDN compromise could inject script. **Fix:** add Subresource Integrity hashes, or self-host these assets.

**8 — Information exposure (Informational).** The production HTML ships a dev version tag and the usual framework fingerprints. Remove the version tag for production and ensure `DEBUG=False` on the server (it is configured to default `False`, which is correct).

### 5.3 What is already done well

- Secrets are externalised to a gitignored `.env` (`SECRET_KEY`, DB, email, `ALLOWED_HOSTS`, `DEBUG`); none are committed.
- `DEBUG` defaults to `False` and `ALLOWED_HOSTS` is explicit.
- Django's CSRF protection is enabled and the contact form includes `{% csrf_token %}`.
- The ORM is used throughout (no raw SQL), so SQL-injection surface is minimal.
- The public CSV-upload endpoint was deliberately removed; data ingestion is admin-only (`@staff_member_required` history) and now admin-managed.
- Password validators are enabled; the app runs as a non-root user under systemd.

### 5.4 Prioritised remediation order

1. Fix the contact `send_mail`/`reply_to` bug (restores the primary CTA).
2. Add anti-spam to the contact form.
3. Add production security-header settings and run `check --deploy`.
4. Harden SSH (keys-only, restrict root) and patch the OS.
5. Add SRI to CDN assets (or self-host); remove the dev version tag.

---

## 6. Appendix A — Version history

| Version | Theme |
|---|---|
| v1.4.x | Initial austro-indo-french redesign; blog/home/about/footer rework; seamless surfaces |
| v1.4.5–1.4.8 | NEM dashboard rework; projects list-rows; editorial featured cards; Stillpoint app created |
| v2.4.9 | "Full version" bump — about rewrite, category changes, hero/footer refinements |
| v2.5.0–2.5.7 | Marginalia system; NEM 7-day mix + 3-month trend; unified page width; random favicon |
| v2.5.8–2.5.9 | Fleur-de-lys, 9-min timer, 4-box stats, larger thumbnails, overlap fixes |
| v2.6.0 | Fleur PNG, Stillpoint default fix; full deployment to live + Parkrun article |

## 7. Appendix B — Deployment runbook (current)

**Site code (on the droplet, as appropriate):**
```
sudo -u thibault git -C /home/thibault/accidental-scientist-portfolio pull origin main
sudo -u thibault /home/thibault/accidental-scientist-portfolio/venv/bin/pip install -r .../requirements.txt
sudo -u thibault bash -c 'cd .../accidental-scientist-portfolio && venv/bin/python manage.py migrate'
sudo chown -R thibault:www-data /var/www/accidental-site/staticfiles   # if collectstatic perms error
sudo -u thibault bash -c 'cd .../accidental-scientist-portfolio && venv/bin/python manage.py collectstatic --noinput'
sudo systemctl restart gunicorn
```
**Articles:** pull `elite-analytics-articles-2026`, then `manage.py import_elite_articles --publish`.
**DB/media (not in git):** create `Project` rows via a `manage.py shell` heredoc; upload audio and NEM CSVs via the Django admin.

## 8. Appendix C — Component inventory

- **Apps:** `portfolio` (public site, blog, projects, contact), `nem_dashboard` (energy tool), `stillpoint` (meditation timer).
- **Key models:** `BlogPost`, `BlogImage`, `Project`, `FuelGenerationData`, `FuelDataUpload`, `GuidedMeditation`.
- **Management command:** `import_elite_articles`.
- **Front-end:** `static/css/style.css` (the design system), per-app JS (`dark_mode.js`, `navbar_shrink.js`, `nem_dashboard/js/fuel_chart.js`, `stillpoint/js/timer.js`), CDN Bootstrap/Chart.js/fonts.
- **Static assets of note:** `coastal_castle.svg`, `fleur-de-lys.png`, favicons.
- **External:** the `elite-analytics-articles-2026` content repository.

---

*End of report.*
