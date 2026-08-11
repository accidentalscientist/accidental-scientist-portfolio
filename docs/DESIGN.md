# Accidental Scientist: Master Design Document

This is the canonical product, design, roadmap, and evolution record for the Accidental Scientist site. It explains why the site exists, how every project works, what each project began as, how it changed, what is intended next, and which ideas remain deliberately uncommitted.

Together with `docs/DEPLOYMENT.md`, it forms the complete documentation system. Do not create project theses, handoff notes, model references, roadmap files, or product specifications as separate durable documents. Temporary working notes must be folded into this file or the deployment runbook and removed before the work is considered complete.

## 1.0 Document control

| Field | Current value |
|---|---|
| Document owner | Thibault Aymonier-Newman |
| Last reviewed | 11 August 2026 |
| Next monthly review | 7 September 2026 |
| Repository | `accidentalscientist2025` |
| Current code version | `2.7.3` |
| Next candidate release | `2.8.0`, subject to release review |
| Production version | Not verified by this document |
| Current branch at review | `main`, aligned with `origin/main` at `50f6c94`, with later local work uncommitted |
| Operational source of truth | `docs/DEPLOYMENT.md` |

The document is reviewed after every release and during the monthly roadmap and parking-lot review. A material change to product purpose, analysis, architecture, data boundaries, visual design, roadmap status, or operating responsibility must update the relevant section here in the same change.

---

## Contents

1. [Part 1: Overview](#part-1-overview)
   - [1.0 Document control](#10-document-control)
   - [1.1 Purpose and audience](#11-purpose-and-audience)
   - [1.2 Portfolio structure](#12-portfolio-structure)
   - [1.3 Design ethos](#13-design-ethos)
   - [1.4 Analytical and product principles](#14-analytical-and-product-principles)
   - [1.5 Project lifecycle](#15-project-lifecycle)
   - [1.6 Architecture and source-of-truth map](#16-architecture-and-source-of-truth-map)
   - [1.7 Versioning and site evolution](#17-versioning-and-site-evolution)
   - [1.8 Article history](#18-article-history)
   - [1.9 Documentation and handoff conventions](#19-documentation-and-handoff-conventions)
2. [Part 2: Projects and apps](#part-2-projects-and-apps)
   - [2.1 Portfolio and publishing](#21-portfolio-and-publishing)
   - [2.2 NEM Dashboard](#22-nem-dashboard)
   - [2.3 NEM Price Predictor Lab](#23-nem-price-predictor-lab)
   - [2.4 StillPoint](#24-stillpoint)
   - [2.5 Portfolio Pulse](#25-portfolio-pulse)
   - [2.6 Life Compass](#26-life-compass)
   - [2.7 World Ledger](#27-world-ledger)
   - [2.8 East Coast Gas System Stress Monitor](#28-east-coast-gas-system-stress-monitor)
   - [2.9 ChargeTrace: NEM Battery Dispatch and Value Stack Explorer](#29-chargetrace-nem-battery-dispatch-and-value-stack-explorer)
3. [Part 3: Roadmap](#part-3-roadmap)
   - [3.1 Roadmap contract](#31-roadmap-contract)
   - [3.2 Scheduled](#32-scheduled)
   - [3.3 Planned](#33-planned)
   - [3.4 Idea phase](#34-idea-phase)
   - [3.5 Roadmap review record](#35-roadmap-review-record)
4. [Part 4: Ideas parking lot](#part-4-ideas-parking-lot)
   - [4.1 Active parking lot](#41-active-parking-lot)
   - [4.2 Monthly review and promotion rules](#42-monthly-review-and-promotion-rules)
   - [4.3 Disposition history](#43-disposition-history)

---

# Part 1: Overview

## 1.1 Purpose and audience

Accidental Scientist is a personal portfolio and publishing system for Thibault Aymonier-Newman. It is aimed primarily at roles in Australia's energy transition, data science, analytics, and commercially applied decision support. The site is intended to demonstrate capability through working evidence rather than claims. It combines long-form analytical writing, interactive data products, and smaller tools that reveal product judgement, technical range, and personal interests.

The site has four jobs:

1. **Establish credibility.** It should make the author's technical, analytical, commercial, and communication skills visible within a few minutes.
2. **Publish durable analysis.** Articles should turn notebooks and research into clear, sourced, editorial work rather than expose unfinished analytical machinery.
3. **Demonstrate products.** Interactive projects should answer a real question and work as products, not as decorative visualisations.
4. **Show range without losing coherence.** Energy systems, commercial intelligence, human performance, and personal execution can coexist when every project is rigorous, purposeful, and clearly framed.

The intended audiences are prospective employers, collaborators, data and energy practitioners, and curious general readers. Individual products may have narrower audiences, such as CEOs and CSMs for Portfolio Pulse or private users for Life Compass, but the portfolio-level experience should remain understandable without specialist onboarding.

## 1.2 Portfolio structure

The site is one Django deployment containing nine public-facing apps with different product roles and persistence boundaries.

| App | Public purpose | Primary audience | Persistence | Product maturity |
|---|---|---|---|---|
| `portfolio` | Home, projects, blog, about, and contact | Employers, collaborators, readers | PostgreSQL and media storage | Mature portfolio shell |
| `nem_dashboard` | Anchor the unified NEM market suite and explain the fuel mix | Energy and data audiences | PostgreSQL populated from daily AEMO SCADA and a quarterly unit register | Functional, automated pipeline ready |
| `nem_price_lab` | Publish leakage-safe NEM price forecasts and keep a visible weekly model record | Energy analysts, forecasting audiences, employers | PostgreSQL plus versioned model runs | Evolving weekly research product |
| `nem_battery_explorer` | Explain five-minute battery operation, observable value, opportunity capture, fleet coverage, and market cannibalisation | Energy traders, strategists, asset owners, analysts, informed readers | PostgreSQL populated from AEMO public files through the shared daily NEM-suite job | Evolving, expanded MVP |
| `gas_monitor` | Explain east-coast gas flows, storage, demand composition, constraints, and data currency | Gas, electricity, strategy, and infrastructure audiences | PostgreSQL populated from AEMO gas sources | Evolving physical-market product |
| `stillpoint` | Provide a quiet meditation timer with optional guided audio | General visitors and human-performance audience | Guided audio in PostgreSQL/media; session history in browser storage | Mature small product |
| `portfolio_pulse` | Turn customer, contract, usage, and ARR data into executive and CSM decisions | CEOs, CS leaders, CSMs | None by design; uploads are request-scoped | Mature portfolio demonstration, not a calibrated production model |
| `life_compass` | Connect personal strategy, projects, daily execution, and reflection | Public demo users and authenticated private user | One JSON document per Django user, mirrored in browser storage | Mature private tool with a separate frontend source repository |
| `world_lens` | Compare present economic power and power potential through adjustable, decomposable rankings | Data-story readers, employers, strategy and policy audiences | Versioned World Bank, WGI, and Harvard Atlas JSON generated by a management command | Functional Giga Dataset v1.0 Data Stories product |

The portfolio shell is the organising layer. The other eight apps are products with their own problem statements. Shared navigation and production standards make them part of one site, while product-specific visual systems are allowed where they improve clarity and intent.

## 1.3 Design ethos

### Shared site identity

The main site's visual system was established in June 2026 as an "austro-indo-french" language:

- **Austrian precision:** strict alignment, restrained geometry, clear hierarchy, and interfaces that feel constructed rather than decorated.
- **Indian warmth:** linen surfaces, terracotta accents, human texture, and ornament used sparingly.
- **French editorial polish:** serif display type, generous line spacing, carefully composed prose, and strong use of typographic hierarchy.

The core light palette uses warm linen `#f4f0e6`, forest ink `#1a2e1a`, forest green `#2d6a2d`, and terracotta `#b84a1a`, with a parallel dark theme expressed through CSS custom properties. Display serif type is reserved for headings and moments of personality. Body copy, controls, analytical explanations, and dense decision content use a legible sans-serif. The August 2026 Portfolio Pulse review made this boundary explicit by removing decorative italics from narrative and analytical statements that had become difficult to scan.

Marginalia supports the identity without becoming content: a terracotta brick ribbon, a faint line-drawing watermark, footer symbols, and a randomly positioned favicon page mark. Decorative elements are `aria-hidden`, low contrast, and removed on narrow screens.

### Product-specific identities

Shared identity does not mean visual uniformity. A project may diverge when the divergence expresses its purpose:

- **Life Compass** uses nautical charts, parchment, brass, navy, and a compass rose because navigation is the product metaphor.
- **StillPoint** reduces ornament and interaction density because quietness is part of the product function.
- **Portfolio Pulse** uses restrained commercial colours and chart semantics because its job is to support decisions, not exhibit illustration.
- **NEM Dashboard** uses stronger chart colour where the comparison itself is the story, particularly renewables versus fossil fuels.
- **ChargeTrace** uses a warm editorial research language with forest green for discharge, terracotta for charging, navy for price, and gold for market context. Its compact cards and serif headings should feel like an independent market brief rather than a generic trading terminal.

The rule is coherence within a product and recognisable relationship to the site, not identical components everywhere.

### Typography and legibility

Editorial type creates identity, but readability wins whenever content must be scanned or acted upon. Italics should be short and rare. Data explanations, health-model descriptions, product theses, and section summaries should use an upright, medium-weight sans-serif. Uppercase labels are acceptable when short. Long uppercase copy, low-contrast microcopy, and decorative type in dense analytical regions are not.

## 1.4 Analytical and product principles

Every project should follow these principles:

1. **Answer a question.** A graph or interaction must help someone orient, decide, compare, or explain.
2. **Name the data boundary.** Reporting periods, stale data, missing fields, inferred values, and unavailable history must be explicit.
3. **Separate observations from estimates.** Actuals, forecasts, heuristics, and illustrative demo values must never be visually or verbally conflated.
4. **Prefer explainability before sophistication.** A transparent baseline is required before a complex model is allowed to claim improvement.
5. **Do not reward a proxy simply because it moved.** Portfolio Pulse, for example, does not treat ARR expansion as proof of customer health.
6. **Make materiality visible.** Counts alone are insufficient when the consequence is financial; percentages alone are insufficient when the base matters.
7. **Show uncertainty honestly.** Model scores are not probabilities unless calibrated against labelled outcomes. Forecasts need issue times, evaluation windows, and benchmarks.
8. **Treat missing data as information.** Missingness may lower completeness, create a visible state, or block a claim. It should not silently remove an inconvenient record.
9. **Design for action and accessibility.** Colour needs a second encoding, controls need keyboard support, mobile must be considered, and motion must respect reduced-motion preferences.
10. **Keep privacy boundaries intentional.** Portfolio Pulse stores nothing; Life Compass private data is user-scoped; public upload paths must not allow visitors to alter shared analytical data.

## 1.5 Project lifecycle

Projects move through a common lifecycle so the design document can distinguish what exists from what is imagined.

| Stage | Meaning | Required documentation |
|---|---|---|
| Idea | Interesting question without an approved delivery commitment | Problem, audience, why it belongs, and promotion trigger in Part 4 |
| Proposed | A scoped concept awaiting an explicit decision | MVP boundary, data requirements, risks, and acceptance criteria |
| MVP | Smallest working release that answers the core question honestly | Purpose, architecture, dataset, limitations, and verification evidence |
| Evolving | Shipped product receiving meaningful feature or design changes | Dated change history and current-state description |
| Mature | Stable product whose next work is maintenance or evidence-driven refinement | Current behavior, operational ownership, and known boundaries |
| Parked | Deliberately paused without being rejected | Reason for pause and evidence needed before resumption |
| Retired | Removed or superseded | Date, replacement, and any migration implications |

A new project should be added only when it strengthens at least one portfolio pillar, has a definable user question, can obtain defensible data, and provides evidence not already demonstrated by an existing project. An article may accompany a project, but an interface should not be built merely to host an article's charts.

### Site-wide definition of done

A project or material feature is ready to release only when:

- its purpose, thesis, audience, current state, and intended user question are documented;
- current behaviour is clearly separated from future ambition;
- data dates, sources, units, estimates, exclusions, and stale states are visible where relevant;
- the simplest credible analytical baseline is present before more complex methods are claimed as improvements;
- automated tests cover the highest-risk behaviour and `manage.py check` passes;
- the real interaction has been checked in a browser at desktop and mobile widths;
- keyboard access, focus visibility, colour contrast, reduced motion, and non-colour encodings have been considered;
- private or uploaded data are not unintentionally persisted or exposed;
- recurring data work, media work, schedules, and recovery steps are recorded in `docs/DEPLOYMENT.md`;
- the affected project evolution table and the site release record are updated; and
- unfinished work is placed once in Part 3 or Part 4 rather than left in a separate handoff note.

## 1.6 Architecture and source-of-truth map

**Runtime stack:** Django 5.2, PostgreSQL, server-rendered templates, static JavaScript, and no site-wide frontend framework. Production runs on a DigitalOcean droplet with Gunicorn and systemd. Environment configuration is held in a gitignored `.env`. Static assets are collected for production, and `django-compressor` bundles the split CSS files outside debug mode.

**Content boundary:** portfolio records, NEM fuel and price observations, ChargeTrace battery intervals and summaries, gas-market observations, guided audio metadata, and private Life Compass documents live in PostgreSQL or media storage. Versioned registries, calculation code, templates, and interface assets travel through git. Uploaded Portfolio Pulse customer data never enters the database.

**Article boundary:** article source lives in the separate `elite-analytics-articles-2026` repository. Each article package contains `article.md`, `metadata.json`, and `figures/`. The idempotent `import_elite_articles --publish` management command imports or updates by slug. The website database contains the published representation, not the research notebooks.

**Life Compass boundary:** the editable TypeScript/Vite source lives in the separate `personal_dashboard` repository. This Django repository contains compiled, hashed assets and Django template shells. A rebuild currently requires manual asset copying and template hash updates.

**Documentation boundary:** `docs/DESIGN.md` is the sole product, analytical design, evolution, roadmap, and parking-lot source of truth. `docs/DEPLOYMENT.md` is the sole release, production, recurring-data, and recovery source of truth. No other durable design or operations documents are maintained. Images referenced by these documents are evidence assets rather than additional sources of truth.

## 1.7 Versioning and site evolution

### Release-number policy

The public site uses `MAJOR.MINOR.PATCH` release numbers. This is a product-release convention rather than a claim of strict library compatibility.

| Change | Bump | Examples |
|---|---|---|
| Fundamental site repositioning, design-system replacement, or incompatible architecture change | Major | `2.x.x` to `3.0.0` |
| New project or substantial user-facing capability | Minor | `2.7.3` to `2.8.0` |
| Bug fix, copy or accessibility improvement, small visual refinement, or operational correction | Patch | `2.7.3` to `2.7.4` |

Every deployment containing a changed code, template, static, dependency, schema, or configuration artifact receives a new site version. Re-running the same release artifact keeps the same version. Article publication and routine project-data refreshes are data operations rather than site deployments: they update publication dates, dataset versions, calculation versions, or freshness timestamps without changing the site version.

For every release:

1. Choose the version before deployment and update the single code constant in `config/context_processors.py`.
2. Update affected project current-state and evolution sections in Part 2.
3. Move delivered roadmap items out of Part 3 and record them in the relevant project evolution table.
4. Add one release-ledger row below with the exact Git tag and commit.
5. Tag the release `vMAJOR.MINOR.PATCH` and deploy that identified artifact.
6. Complete the post-deployment checks in `docs/DEPLOYMENT.md` and mark the release verified.

Project dataset, registry, schema, and calculation versions remain separate from the site release. For example, a ChargeTrace registry revision can be published in a routine data operation without pretending the entire website has become a new software release.

### Release ledger

| Version | Released | Scope | Projects affected | Git reference | Production verification |
|---|---|---|---|---|---|
| `2.6.0` | 25 Jun 2026 | Visual identity overhaul, StillPoint, and NEM reframing | Site shell, NEM, StillPoint | Historical tag or commit not recorded here | Historical release |
| `2.7.0` | 26 Jun 2026 | Production trust, metadata, indexing, and discoverability | Site-wide | Historical tag or commit not recorded here | Historical release |
| `2.7.1` to `2.7.3` | 27 Jun 2026 | Navigation, footer, split CSS, and visible versioning | Site-wide | Historical tag or commit not recorded here | Historical release |
| Unreleased candidate `2.8.0` | Not deployed | Portfolio Pulse, Life Compass, World Ledger, Price Predictor Lab, Gas Monitor, ChargeTrace, and later refinements | Site-wide | Local work after `50f6c94` | Not verified |

Starting with the next release, the Git reference must be exact and optional release evidence may include before-and-after screenshots in `docs/images/releases/<version>/`. Git tags preserve the working implementation; screenshots preserve the visible iteration.

### Dated site evolution

Dates below are based on repository history unless explicitly identified as content publication dates.

| Date | Change | Why it mattered |
|---|---|---|
| 11 Apr 2025 | Fresh repository reset and Django portfolio scaffold | Established the current codebase and homepage foundation |
| 16 Apr 2025 | Blog, projects, contact, templates, and dark mode added | Converted a static portfolio into a small publishing application |
| 17 Apr 2025 | Environment-based settings, seed data, and static/media structure | Made local and production behavior separable and repeatable |
| 10 Jun 2025 | Major site and blog presentation redesign | Shifted from a basic portfolio toward editorial data storytelling |
| 26 Jul 2025 | Markdown, multiple article images, and styling improvements | Enabled richer long-form articles |
| 4 Aug 2025 | NEM fuel dashboard introduced | Added the first major interactive energy product |
| 24 Jun 2026 | Curated article-package publishing and final article batch | Created a reproducible boundary between analytical source and public prose |
| 25 Jun 2026 | v2.6 visual overhaul, StillPoint added, NEM reframed | Established the current design identity and expanded the portfolio beyond energy charts |
| 26 Jun 2026 | v2.7 production trust and discoverability work | Improved deployability, indexing, metadata, and credibility |
| 27 Jun 2026 | v2.7.1 to v2.7.3 navigation, footer, CSS splitting, and visible versioning | Made the design system more maintainable and the live version inspectable |
| 7 Jul 2026 | Portfolio Pulse and Life Compass added; Commercial Intelligence taxonomy introduced | Added commercial analytics and personal strategy products |
| 8 Jul 2026 | Life Compass authentication and per-user persistence | Turned a public demo into a usable private tool |
| 13 to 14 Jul 2026 | Life Compass phases, dependency cleanup, contact-form fix | Simplified execution workflows, removed 54 unused dependency packages, and stopped silent email failure |
| 30 Jul 2026 | Life Compass execution overhaul, StillPoint roadmap completion, Portfolio Pulse repurposing | Matured three products through direct product review rather than feature accumulation |
| 4 Aug 2026 | StillPoint visual redesign and Portfolio Pulse scoring-system redesign | Added the current three-model health architecture and refined product presentation |
| 10 Aug 2026 | ChargeTrace built, expanded, and documented as an independent NEM battery research product | Added weekly AEMO ingestion, 17-asset coverage, opportunity benchmarking, fleet context, market-structure analysis, and a first-principles strategy guide |
| 11 Aug 2026 | NEM products unified and daily data operations implemented | Renamed the parent NEM Dashboard, nested price, battery and gas views, added direct fuel-SCADA ingestion, and created one 09:00 daily server workflow |

## 1.8 Article history

The local database snapshot reviewed on 4 August 2026 contains the following published articles. Publication dates are content metadata; the 24 June 2026 import date is the implementation milestone for the current package-based publishing system.

| Published | Article | Portfolio pillar |
|---|---|---|
| 28 Jul 2025 | Parkrun Performance Analysis | Human Performance |
| 28 Jul 2025 | Climate Change Part 4 | Energy Systems |
| 24 Jun 2026 | Australia's Grid Transition: What 25 Years of NEM Data Reveals | Energy Systems |
| 24 Jun 2026 | Mapping Australia's Power System: Where the Transition Is Taking Shape | Energy Systems |
| 24 Jun 2026 | Australia's Energy Balance: Consumption, Supply and the Petroleum Challenge | Energy Systems |
| 24 Jun 2026 | Who Is Really Leading the Green-Energy Transition? | Energy Systems |
| 24 Jun 2026 | Climate Evidence: From Australia's Power System to Global Temperature Records | Energy Systems |
| 24 Jun 2026 | Climate Risk, Emissions and Policy: From Rising Seas to National Transition Pathways | Energy Systems |
| 24 Jun 2026 | The Weekly Energy Fingerprint: What Household Demand Tells Us About the Grid | Energy Systems |
| 24 Jun 2026 | Where the World Is Going: Demography, Prosperity and Economic Resilience | Data Stories |
| 24 Jun 2026 | Fifteen Years of the Premier League: What Sustained Success Looks Like | Human Performance |
| 24 Jun 2026 | The City Inequality Question: What Metropolitan Data Reveals | Data Stories |
| 25 Jun 2026 | The Long Run: A Parkrun Record of Progress, Patience and a Mid-2021 Breakthrough | Human Performance |

New articles should be recorded here when published, including publication date, package-import date if different, category, and whether they introduce a new dataset, method, or project dependency.

## 1.9 Documentation and working conventions

Durable working facts live beside the relevant system:

- Production commands remain in `docs/DEPLOYMENT.md`.
- Product-specific build constraints live in the corresponding Part 2 section.
- Unfinished, authorised work belongs in Part 3.
- Uncommitted questions and concepts belong in Part 4.
- Dated reasoning belongs in each project's evolution table, not in a separate decision log.
- Model formulas, data contracts, and product theses belong in the relevant Part 2 project record.
- Data refresh commands, upload steps, schedules, verification, and recovery belong in `docs/DEPLOYMENT.md`.

Process preferences:

- The user performs `git push` and production SSH commands unless they explicitly request otherwise.
- Do not raise deployment unprompted.
- Never render private email addresses client-side or repeat them in documentation.
- Avoid em dashes in user-facing copy and documentation.
- Preserve unrelated working-tree changes.
- Before changing an app, identify its real source of truth. Life Compass source is not the compiled Django asset directory.

As of 4 August 2026, local `main` matches `origin/main` at `50f6c94`; production deployment of later local changes has not been asserted by this document. The earlier 14 July handoff warning about possibly unpushed commits is historical rather than a current repository mismatch.

---

# Part 2: Projects and apps

Every project record uses the same core structure: Purpose, Project thesis, Original MVP, Current state, Product evolution, Roadmap summary, and Known boundaries or limitations. Supporting analytical or architectural sections may sit between Current state and Product evolution. Evolution tables use the site release where it is known; older untagged work is marked as pre-version-history, and current local work is marked as the `2.8.0` candidate until it is released.

## 2.1 Portfolio and publishing

| Field | Current value |
|---|---|
| Status | Mature portfolio shell |
| Introduced | April 2025 |
| Last materially changed | 14 July 2026, unreleased after `2.7.3` |
| Public routes | `/`, `/projects/`, `/blog/`, `/about/` |
| Application | `portfolio` |
| Data operation | Article import, project records, contact configuration, and media; see `docs/DEPLOYMENT.md` |
| Roadmap references | `SITE-S01` to `SITE-S03`, `SITE-P01`, `SITE-P02` |

### Purpose

The portfolio app is the public front door and publishing layer. It should establish credibility quickly, make projects easy to discover, and let long-form analysis remain the deepest evidence on the site. It is not merely navigation around the tools; it provides the editorial and professional context that explains why those tools exist.


### Project thesis

A portfolio is more credible when claims about technical, analytical, commercial, and communication ability are supported by working products and durable writing. The shell should make that evidence understandable within minutes while still rewarding deeper inspection.

### Original MVP

The April 2025 MVP contained a Django homepage, project and blog models, basic templates, a contact form, and dark mode. Seed data made the first deployment reproducible. The initial goal was functional presence: a portfolio that could display work and receive contact messages.

### Current state

`portfolio/models.py` defines:

- `Project`: title, slug, description, category, image, URL, and creation date;
- `BlogPost`: title, slug, summary, key takeaway, Markdown content, image, publication and update dates, status, category, featured flag, external URL, and computed reading time;
- `BlogImage`: ordered article figures and captions; and
- `Contact`: submitted message records.

The public experience includes the home page, full-width project rows, blog category filtering, article detail pages, an about page, and contact. Article Markdown is rendered with `markdown2`; `[[image1]]` placeholders resolve to ordered `BlogImage` records. The project layout deliberately uses full-width rows rather than a card grid so one project and many projects both look intentional.

The category system is shared between writing and projects: Energy Systems, Data Stories, Human Performance, and Commercial Intelligence. This creates space for energy-market work, broader analysis, sport and running, and commercial products without an unhelpful catch-all category.

### Product evolution

| Site release | Date | Change | Product rationale |
|---|---|---|---|
| Pre-version-history | 11 to 17 Apr 2025 | Scaffold, models, templates, contact, dark mode, seed data | Establish a complete working portfolio rather than a static landing page |
| Pre-version-history | 10 Jun 2025 | Site and article presentation rebuilt | Make analytical writing central rather than secondary |
| Pre-version-history | 26 to 28 Jul 2025 | Markdown, multiple images, blog styling, dark-mode fixes | Support real data stories with figures and longer structure |
| `2.6.0` to `2.7.3` | 24 to 27 Jun 2026 | External article-package importer, editorial redesign, category and footer refinement | Separate research source from publishable output and create a coherent visual identity |
| Candidate `2.8.0` | 7 Jul 2026 | Commercial Intelligence category and rotating project exposure | Give Portfolio Pulse and Life Compass an explicit portfolio home |
| Candidate `2.8.0` | 14 Jul 2026 | Contact delivery made fail-loud | Stop successful-looking submissions from disappearing when configuration is missing |

### Contact and operational boundary

Two different contact defects were fixed. An earlier `send_mail(reply_to=...)` call used an unsupported argument and raised. The later defect was subtler: an unset `CONTACT_EMAIL` produced an empty recipient list, and `EmailMessage.send()` returned zero without raising, so the site showed success while sending nothing. The view now validates configuration and treats zero sends as failure.

The receiving address and optional branded sender alias are deployment configuration, not product code. `DEFAULT_FROM_EMAIL` should remain unset unless the branded address has been verified with the email provider. Domain forwarding is parked until the user chooses a provider. Private recipient addresses must never appear in public templates or this document.

### Roadmap summary

The next site-shell work is operational trust and maintainability: dependency and security review, production contact verification, static-asset cache busting, continuous integration, and a cross-site accessibility pass. The authoritative items and their status live in Part 3.

### Known boundaries

- The project catalogue mixes database records with code-defined routed products. A presentation layer keeps the NEM Dashboard first, nests its specialist views, and ranks every other project by hidden update metadata. Production database rows are renamed by migration rather than by an undocumented admin edit.
- Contact delivery still depends on correct production environment configuration.
- Article package source remains a separate repository and must be available for editorial updates.

## 2.2 NEM Dashboard

| Field | Current value |
|---|---|
| Status | Unified four-view market suite; daily automation ready for production activation |
| Introduced | 4 August 2025 |
| Last materially changed | 11 August 2026, candidate release `2.8.0` |
| Public route | `/nem/` |
| Application | `nem_dashboard` |
| Data operation | Unified daily 09:00 refresh and direct AEMO SCADA fuel ingestion; see `docs/DEPLOYMENT.md` |
| Roadmap references | `NEMF-S01`, `NEM-S01`, `NEM-I01` |

### Purpose

The NEM Dashboard is the public home for four connected market views: fuel mix, price forecasting, battery dispatch and east-coast gas conditions. Its portfolio value is market literacy across the physical and commercial chain while each child application retains its own models, method and source boundary.

### Project thesis

Recent generation mix becomes useful evidence only when it is bounded by an explicit period, expressed in correct energy units, separated from longer structural trends, and honest about whether the underlying data are current.

### Original MVP

The August 2025 MVP introduced a database-backed fuel-generation dashboard and admin CSV upload. Its main weakness was analytical framing: it summed `supply_mw` across all available history and defaulted to NSW, creating a plausible but misleading headline that looked current and market-wide.

### Current state

`FuelGenerationData` stores one daily state/fuel energy total. `refresh_fuel_mix` reads AEMO's quarterly Generation Information workbook, maps operating and commissioning DUIDs to a public fuel taxonomy, integrates positive five-minute Dispatch SCADA into daily MWh, and rejects coverage below 95%. The old `FuelDataUpload` path remains a repair fallback rather than the normal operating method.

The current page uses an explicitly dated seven-day generation window and a separate three-month renewables-versus-fossil trend. Server-side payloads are prepared for NEM and each state so the region selector can cycle without a page request. Manual selection pins the region. Headline statistics show seven-day generated energy, renewable share, coal share, and gas share. A grouped stacked bar and per-fuel breakdown explain composition.

Battery is labelled as storage rather than renewable generation. The three-month trend uses strong green and red lines because the comparison is the analytical story. The page does not claim to be a live feed.

The shared tab strip mounts Fuel mix at `/nem/`, Price Predictor Lab at `/nem/price-lab/`, ChargeTrace at `/nem/charge-trace/`, and FlowTrace at `/nem/flow-trace/`. Previous `/charge-trace/`, `/gas/`, `/battery-explorer/`, and `/nem/battery-explorer/` URLs are permanent redirects. One orchestration command updates all four source families at 09:00 Australia/Sydney every day; the weekly price forecast itself is created only for a missing Sunday origin.

### Product evolution

| Site release | Date | Change | Product rationale |
|---|---|---|---|
| Pre-version-history | 4 Aug 2025 | First substantial NEM dashboard introduced | Add a working energy-data product |
| `2.6.0` | 25 Jun 2026 | Rebuilt around a bounded seven-day window and three-month trend | Replace misleading lifetime aggregation with an honest reporting frame |
| `2.7.0` | 26 Jun 2026 | Production trust and discoverability pass | Improve public credibility and operational framing |
| Candidate `2.8.0` | 11 Aug 2026 | Unified NEM suite, direct SCADA fuel pipeline, daily scheduler | Replace disconnected cards and manual fuel uploads with one navigable and maintainable operating system |

### Roadmap summary

The immediate remaining correction is a unit and payload-name audit. The products are now combined at the navigation and operations layers while remaining separate Django applications, so a failure or method change in one source family does not couple its database schema to the others. See Part 3.

### Known boundaries

- Production timer activation and first-run observation still require server access.
- The seven-day total is energy in MWh. Detailed fuel rows still need an explicit unit audit so aggregated values are not labelled MW.
- Internal payload names such as `total_mw` may preserve old terminology and should be corrected at the aggregation boundary.
- AEMO's generation register is quarterly. `NEM_GENERATION_REGISTER_URL` must be updated when a new workbook is reviewed; daily dispatch ingestion otherwise requires no manual upload.

## 2.3 NEM Price Predictor Lab

| Field | Current value |
|---|---|
| Status | Evolving weekly research product |
| Introduced | 6 August 2026, unreleased after `2.7.3` |
| Last materially changed | 6 August 2026 |
| Public route | `/nem/price-lab/` |
| Application | `nem_price_lab` |
| Data operation | Weekly price and weather ingestion followed by forecast publication; see `docs/DEPLOYMENT.md` |
| Roadmap references | `NEM-S01`, `NEMP-P01`, `NEM-I01` |

### Purpose

The fuel mix dashboard explains how electricity is generated. The Price Predictor Lab asks what it costs, and whether that cost can be anticipated a week out. Its portfolio value is forecasting method rather than forecasting accuracy: leakage control, an honest baseline ladder, published-and-never-revised predictions, and a scoring record that includes the weeks the models lost.

The two pages are a single product with two views. `nem_dashboard` remains the home view; the lab is a second view reached from a tab strip on both pages. It is a separate Django app (`nem_price_lab`) because it shares no models, no cadence and no analytical claims with the fuel mix, but it is mounted under the same `/nem/` prefix and is intended to fold into a unified NEM dashboard later.

### Project thesis

> Australia's electricity market publishes a price every five minutes, for every region, forever. That makes it one of the most forecastable public datasets in the country, and one of the easiest to lie about, because anyone can fit a model to the past and present the fit as foresight.
>
> This project does the opposite. Every Sunday it publishes a seven-day forecast of the wholesale spot price for each NEM region, and the following Sunday it scores that forecast against what actually cleared. Predictions are never revised. The record accumulates in public, including the weeks the models lose.
>
> The ladder starts at the most obvious guess available, "assume this week repeats last week", and every further model must earn its place against that baseline. So far the cheapest baseline is winning, and that is reported plainly rather than buried beneath a tuned score.
>
> What this demonstrates is method, not accuracy: separating what was known at forecast time from what was learned afterwards, publishing the coefficients a model actually fitted, and treating a loss as evidence rather than something to conceal. A page that only shows its current model is making a claim. One that shows what changed, and why, is offering proof.

*(≈200 words, reproduced on the page itself. Keep the two in step.)*

### Original MVP

Published at `/nem/price-lab/`. All five NEM regions, 30-minute intervals, seven-day horizon, forecast origin pinned to Sunday 00:00.

Six models form a ladder, ordered cheapest to most elaborate. Each has to beat the one before it to justify existing:

| Model | Data needed | Fitted | What it does |
|---|---|---|---|
| Same as last week | price only | nothing | Repeats the price from the same half hour seven days earlier |
| Median of last 4 weeks | price only | nothing | Median of that half hour across four weeks, so one spike week cannot dominate |
| Last week + temperature | price, temperature | 12 numbers | Adds a fitted adjustment for the forecast change in heating and cooling degrees |
| Random forest | price, demand, calendar, temperature | 300 trees | Ensemble over a 27-feature matrix; stable, but structurally cannot extrapolate past its training range |
| Gradient boosting | as above | 400 boosted trees | Trees fitted in sequence on each other's residuals; sharper and easier to overfit, so it uses early stopping |
| Neural network | as above, standardised | two hidden layers | Smooth nonlinear model that can extrapolate and therefore requires explicit prediction bounds |

The two baselines need no data beyond the price history and no fitting at all, which is the point: they are what everything else must beat. The tree models depend on scikit-learn, kept in `requirements-ml.txt` and deliberately out of production, since training happens offline and the page serves stored predictions.

Models are individually selectable on the chart. The default view shows the baseline and one model, because five lines at once is unreadable.

### Current state and model reference

The current product predicts 336 half-hour intervals per region for the seven days after a Sunday 00:00 NEM-time origin. At the origin, a model may use settled price history, calendar information, and weather forecasts that were actually available. Realised target-week demand, generation, prices, and weather are forbidden.

Six models are retained because each represents a distinct level of cost and explainability:

| Model | Definition and boundary |
|---|---|
| Seasonal naive | `prediction[t] = actual[t - 7 days]`; the mandatory no-fit benchmark |
| Four-week rolling median | Median of the same half-hour one, two, three, and four weeks earlier; robust to one spike week |
| Temperature-adjusted naive | Seasonal naive plus separately fitted heating- and cooling-degree changes across six time-of-day bands; zero intercept and at least 40 usable pairs per band |
| Random forest | 300 trees, maximum depth 14, minimum eight samples per leaf; stable but unable to extrapolate outside training targets |
| Gradient boosting | 400 iterations, depth six, learning rate 0.06, L2 regularisation, and early stopping on a 15% temporal training split |
| Neural network | Standardised 64- and 32-unit ReLU layers with Adam and early stopping; capable of extrapolation and therefore explicitly bounded to the observed training range |

The learned models fit `asinh(price)` because NEM prices are signed and extremely skewed. Predictions are inverted with `sinh`, constrained by the training range, and never allowed below the stable market floor of -$1,000/MWh. Tree and neural models consume cyclic hour, weekday and month encodings; forecast horizon; six time bands; one- to four-week price lags and their summary statistics; one-week demand lag; and forecast, lagged, heating, cooling, and change-in-temperature features. Rows missing a required input are dropped rather than silently imputed.

Training uses observed temperature as a proxy where archived forecasts do not exist, which creates known optimism. Live and backtest runs store forecast and observed weather separately, and any observed-weather fallback is labelled optimistic. The market-wide NEM series is demand-weighted so small and large regions do not move the headline equally.

| Source | Purpose |
|---|---|
| AEMO monthly Price and Demand CSV | Regional RRP and total demand; five-minute rows are averaged to half hours |
| Open-Meteo forecast API | Live seven-day regional-capital temperature forecast |
| Open-Meteo historical forecast API | Forecast vintages that were available at past origins |
| Open-Meteo archive API | Observed historical temperature |

Training-only scikit-learn dependencies live in `requirements-ml.txt`, not the production requirements. The web application serves stored forecast rows and does not import the training module. Operators can inspect the exact price, weather, feature, forecast, and score records with `export_price_lab_data`; the command is documented in `docs/DEPLOYMENT.md`.

The adjustment record is part of the product. On 6 August 2026 the temperature model was split into heating and cooling effects after one slope averaged opposite seasonal responses toward zero; calendar features were corrected from UTC to fixed UTC+10 NEM time; neural-network predictions were bounded after `sinh` inversion magnified extrapolation; and archived-forecast ingestion was extended to remove a false live-edge weather gap.

### Design decisions

**Thirty minutes, not five.** Five-minute dispatch data is averaged up on ingest. A seven-day-ahead forecast has no business at five-minute resolution, and averaging six 5-minute prices into a half hour reproduces how the trading price was defined before Five Minute Settlement, so the pre- and post-2021 eras stay coherent.

**NEM time is a fixed UTC+10 offset.** It does not observe daylight saving, so the project's `Australia/Sydney` setting is deliberately not used for market timestamps. Using it would silently move half the year's observations by an hour.

**Intervals are labelled by their end.** AEMO's `SETTLEMENTDATE` marks the end of an interval, so the half hour stamped 00:30 covers 00:05-00:30. The model field is named `interval_end` rather than leaving a silent off-by-one, and every calendar question is asked of the interval's start.

**Forecast temperature and observed temperature are stored as separate rows.** Training or scoring a forward model against temperature that actually occurred is leakage, because on the day the call is made only a forecast exists. Runs record which they used, and a run that fell back to observed temperature is labelled optimistic on the page rather than passing as clean.

**No new dependencies.** The models are plain Python over dictionaries. Adding an ML stack to fit twelve coefficients would reverse the July 2026 dependency cull for no analytical gain, and a model a reader can reproduce in a spreadsheet is worth more here than a black box with a better score.

**Runs are never overwritten.** Each Sunday adds rows. The archive of what was predicted, and when, accumulates on its own, which is what makes the following week's review possible without separate bookkeeping.

### First results

Eleven weekly origins backtested against real data, using archived forecast temperature rather than reanalysis:

- The **median of last four weeks beat the seasonal-naive baseline in all five regions**, with weekly skill from +5% to +54% and a mean near +20%. It costs no extra data at all.
- The **temperature model did not beat it anywhere**. Weekly skill against the baseline ranged from +13.7% to −20.5% in NSW, and it was negative in Queensland.

This is the honest headline and it is published as such: the cheapest baseline wins, and the model that consumed an extra data source did not earn its place. That result is more useful portfolio evidence than a tuned score would be.

A defect was found and corrected during the first backtest. The initial temperature model used a single dollars-per-degree coefficient per band. Measured on NSW data that specification returned near-zero coefficients, because demand responds to temperature in a V rather than a line: the morning-ramp response was **+$11.57/°C in summer and −$12.74/°C in winter**, which one slope averaged to **+$1.47**. Splitting the driver into heating and cooling degrees against an 18 °C base let each side keep its own sign and gave the model real, if still insufficient, signal.

### Product evolution

| Site release | Date | Change | Product rationale |
|---|---|---|---|
| `Candidate 2.8.0` |  6 Aug 2026 | App, ingestion, three-model ladder and public page shipped | Add a forecasting product that demonstrates method rather than claiming accuracy |
| `Candidate 2.8.0` |  6 Aug 2026 | Single temperature coefficient replaced with a heating/cooling split | The original specification averaged two opposite seasonal effects to zero |
| `Candidate 2.8.0` |  6 Aug 2026 | Derived market-wide NEM series added; region selector now auto-cycles from NEM | Match the fuel-mix dashboard's rhythm so the two views read as one product |
| `Candidate 2.8.0` |  6 Aug 2026 | Forecast chart enlarged; models made individually selectable | Three model lines at once was unreadable; the baseline plus one model is the honest default |
| `Candidate 2.8.0` |  6 Aug 2026 | Review section rebuilt as Performance: last week plus running average since a stated date | One week can be won by luck; the running average is the number that carries weight |
| `Candidate 2.8.0` |  6 Aug 2026 | Plain-English explanation of "skill" added | A percentage nobody can interpret is not a published result |
| `Candidate 2.8.0` |  6 Aug 2026 | Coefficients charted as well as tabulated | The shape of the temperature response across the day is the finding; a table hides it |
| `Candidate 2.8.0` |  6 Aug 2026 | "What this is not" section removed and folded into the opening thesis | The framing belongs where a reader starts, not as a footnote after the evidence |

### Roadmap summary

The operating priority is to establish a durable weekly publish-and-review record. The next planned model is a leakage-safe one-day-ahead forecast using information that exists at that horizon, including AEMO pre-dispatch. Combining the fuel and price interfaces remains an idea until both cadences are stable. See Part 3.

### Known boundaries

- Ingestion is manual and admin-controlled, matching the fuel mix dashboard. Automation is a scheduling decision, not a code change; see Part 3.
- One representative weather point per region. A population-weighted multi-point average would be more faithful.
- The market price cap is deliberately not hardcoded because it is indexed annually; only the stable −$1,000 floor is applied.
- Weekly origins mean few independent observations: a year of operation is 52 origins, not 52 × 336.
- Spikes are not forecastable at this horizon and the product says so.

## 2.4 StillPoint

| Field | Current value |
|---|---|
| Status | Mature small product |
| Introduced | Release `2.6.0`, 25 June 2026 |
| Last materially changed | 4 August 2026, unreleased after `2.7.3` |
| Public route | `/stillpoint/` |
| Application | `stillpoint` |
| Data operation | Optional guided MP3 upload through Django admin; see `docs/DEPLOYMENT.md` |
| Roadmap references | None active |

### Purpose

StillPoint is a deliberately small product: a quiet place to sit. Its value in the portfolio is restraint. It demonstrates state management, audio behavior, background-tab reliability, accessibility, and product editing that removes unnecessary quantification rather than continuously adding features.

### Project thesis

A meditation tool demonstrates stronger product judgement when it protects quietness, elapsed-time reliability, and accessibility instead of maximising settings, statistics, streaks, or engagement mechanics.

### Original MVP

The 25 June 2026 MVP shipped one Django model, one view, and one page. `GuidedMeditation` stores title, description, MP3 audio, and display order. Master mode provided a silent countdown with presets; Guide Me mode followed uploaded audio. An SVG ring visualised remaining time and browser-generated bells marked session boundaries.

### Current state

Master mode is self-timed with the current preset set intentionally reduced after review. Guide Me mode follows an admin-uploaded MP3. Audio upload is MP3-only; the earlier acceptance of a 46 MB WAV was rejected as an unsuitable web policy.

The timer uses real end-time calculations, Wake Lock where available, a timeout backstop, and `visibilitychange` recovery so background throttling cannot silently prevent completion. Session history is held locally in the browser. The interface uses a small three-day completion indicator rather than streak totals or accumulated minutes. Bells occur automatically during Master sessions without a settings panel. The breathing animation affects the ring itself with a restrained green glow. The August 2026 redesign further strengthened the minimal, quiet visual system.

### Product evolution

| Site release | Date | Change | Product rationale |
|---|---|---|---|
| `2.6.0` |  25 Jun 2026 | Initial product shipped | Add a focused human-performance tool |
| `Candidate 2.8.0` |  30 Jul 2026 | Background-tab completion fixed | Tie timer completion to elapsed time rather than animation scheduling |
| `Candidate 2.8.0` |  30 Jul 2026 | Wake Lock, local history, accessibility, interval bells, guidance, and breathing work | Complete the functional improvement roadmap |
| `Candidate 2.8.0` |  30 Jul 2026 | Stats and controls simplified; preset set reduced; naming corrected to StillPoint | Restore the stoic brief after the feature pass became too configurable |
| `Candidate 2.8.0` |  4 Aug 2026 | Full visual redesign | Make the quiet product feel intentional and coherent |

### Design rationale and boundaries

- The timer is narrower and more centred than the portfolio pages because immersion is part of the task.
- Web Audio generates Master-mode bells, avoiding an unnecessary media dependency.
- Guided audio persists in Django/media; local session history is not a cross-device account feature.
- A past metadata bug caused guided-audio duration to override the Master default. Duration reads are now mode-specific.

### Roadmap summary

StillPoint has no active roadmap item. New work should be evidence-driven maintenance or enter Part 3 or Part 4 before implementation.

## 2.5 Portfolio Pulse

| Field | Current value |
|---|---|
| Status | Mature portfolio demonstration; not a calibrated production model |
| Introduced | 7 July 2026, unreleased after `2.7.3` |
| Last materially changed | 4 August 2026 |
| Public route | `/pulse/` |
| Application | `portfolio_pulse` |
| Data operation | None; uploaded CSVs are request-scoped and discarded |
| Roadmap references | `PP-P01`, `PP-I01` |

### Purpose

Portfolio Pulse turns a book of recurring-revenue customers into three decisions:

> **See the shape of the book, decide where to intervene, then understand how the result was made.**

### Project thesis

It is designed for CEOs, customer-success leaders, and CSMs. The governing health thesis is that a Customer Success Health Score should provide an evidence-based estimate of a customer's likelihood to renew, expand, and realise value. It should combine weighted evidence across product adoption, business outcomes, engagement, support experience, commercial position, and stakeholder strength. It should move upward and downward as behavior changes, with Healthy, Watch, and Critical thresholds that trigger timely and consistent action. Its purpose is not to describe the relationship perfectly; it is to support action.

The present implementation only partially operationalises that thesis because the available CSV does not contain direct business-outcome or stakeholder-strength fields and does not contain labelled future outcomes. The models are transparent action-ranking indices, not calibrated churn probabilities.

### Original MVP

Portfolio Pulse first shipped on 7 July 2026 as a stateless CSV dashboard with a snapshot upload, optional revenue timeline, one contextual health score, KPI strip, and ten charts. The original product mixed current portfolio state with historical performance and used several measures later rejected during product review: NRR, GRR, MRR language, Revenue versus Risk, Spend Trajectory, ARR Bridge, stacked revenue groups, and a separate risk-versus-health framing.

The MVP proved the request-scoped upload architecture and scoring pipeline, but its information architecture was graph-led rather than question-led. Several visuals were technically valid without being operationally useful.

### Current state

The redesign completed across 30 July and 4 August 2026 presents one page with three decision views:

1. **Portfolio Outlook:** the executive view of scale, health, concentration, customer maturity, and renewal exposure.
2. **Customer Action Centre:** the CSM view of which six customers require intervention and why.
3. **Revenue Story:** the historical report explaining how ARR and observable customer signals moved.

The page moves from orientation to intervention to explanation. Active positive-ARR customers drive current portfolio and action views. Zero-ARR former customers remain in historical calculations so churn is not erased from the revenue story.

### Product evolution

| Site release | Date | Change | Product rationale |
|---|---|---|---|
| `Candidate 2.8.0` |  7 Jul 2026 | Initial stateless Portfolio Pulse shipped | Demonstrate commercial intelligence through a working customer-success dashboard |
| `Candidate 2.8.0` |  30 Jul 2026 | Full product redesign and repurposing | Replace graph accumulation with three decision products and ARR-only language |
| `Candidate 2.8.0` |  30 Jul to 4 Aug 2026 | Executive summaries, contract runway, tenure, intervention cards, revised charts, deterministic sample data, and UI refinements | Answer explicit CEO and CSM questions and remove low-value measures |
| `Candidate 2.8.0` |  4 Aug 2026 | Plain Pulse, Signal Compass, and Retention Horizon introduced | Let users choose an explainable scoring method at increasing complexity |
| `Candidate 2.8.0` |  4 Aug 2026 | Sample preparation separated from analysis Build; selected-model panel redesigned | Make model choice explicit and prevent silent recalculation |
| `Candidate 2.8.0` |  4 Aug 2026 | Decorative italics removed from decision copy | Prioritise scanning and legibility in an analytical product |

### Architecture and privacy

Portfolio Pulse is stateless. Uploaded customer files are parsed, scored, aggregated, rendered, and discarded within the request. There is no customer database, login, saved history, or CRM integration.

The core modules are:

- `parsing.py`: validates Snapshot and Timeline CSVs;
- `metrics.py`: enriches accounts and derives temporal values;
- `scoring.py`: contains pure account-scoring functions and named constants;
- `aggregate.py`: creates KPIs, queues, and chart payloads;
- `views.py` and `forms.py`: handle request flow and validation;
- `sample_data.py`: produces deterministic demonstration data; and
- `pulse_charts.js`: renders Chart.js views from safely embedded JSON payloads.

The code uses the Python standard library rather than pandas because account volumes are modest and the smaller dependency surface improves transparency. Chart data use Django `json_script`, avoiding manual interpolation into executable JavaScript.

### Upload and build flow

The upload surface has two panes. Snapshot and Timeline files plus sample resources appear on the left. The health-model selector and Build action appear on the right and stack below on mobile.

- **Snapshot CSV is required for user data.** It contains one current record per account.
- **ARR Timeline CSV is optional.** It contains monthly ARR and optional usage history.
- **Load sample portfolio prepares data only.** It shows a Sample Portfolio Ready state without rendering analysis.
- **Build my Portfolio Pulse performs analysis.** Changing the model updates its descriptor but does not change the dashboard until Build is clicked.
- **Nothing uploaded is stored.** A new build with uploaded data requires the files again.

### Portfolio Outlook

Portfolio Outlook is the one-minute executive summary. It contains eight populated summaries:

| Summary | Question answered |
|---|---|
| Current ARR | What is the active recurring-revenue base? |
| Portfolio health | How healthy is the ARR-weighted book? |
| ARR planning window | How much ARR renews within 18 months? |
| 12-month ARR change | Is ARR growing or shrinking? |
| Top-five concentration | How dependent is the book on five customers? |
| Immediate renewals | How much ARR and how many accounts renew within six months? |
| Critical plus Watch ARR | How much current ARR is exposed? |
| Five-year customer ARR | How much ARR comes from customers retained at least five years? |

Without a Timeline, One-Year Contract ARR replaces the historical change tile. Critical, Watch, and Healthy counts and ARR appear in a health-band strip.

The Outlook charts are:

- **The Value Ladder:** divides the ARR-ranked active portfolio into Gold, Silver, and Bronze cohorts and compares average ARR. Hover adds count, total, and range.
- **The Renewal Horizon:** groups current ARR into 0 to 6 months, 6 to 18, 18 to 36, and 36+ months. Hover includes account count, secured contract value, three-year re-sign value, and one-year-term ARR.
- **The Revenue Skyline:** shows up to the 50 largest active customers, ordered by ARR and coloured by health. Names are hover detail, not axis clutter.
- **Customer Roots:** groups active ARR by tenure below one year, one to three, three to five, five to ten, and more than ten years.
- **Sector Weather:** splits each industry's ARR into Critical, Watch, and Healthy, with average health, account count, and largest-customer share on hover.

### Customer Action Centre

The action view follows the principle that attention should follow financial consequence, not the loudest signal. The Intervention Queue is restricted to six accounts and combines ARR exposure, health severity, and renewal proximity. Each card includes rank, owner, health, band, ARR, runway, QBR age, missing-QBR treatment, contract term, secured value, leading drivers, and completeness.

Supporting views are:

- **The Health Footprint:** account count by band with ARR written in each bar.
- **The Executive Contact Gap:** ARR versus days since last QBR, coloured by contract runway from red through deep green.
- **Commercial Tides:** five largest ARR-dollar decliners and growers over the trailing twelve months on a symmetrical axis.
- **The Early-Warning Map:** ARR change and usage change on fixed -100% to +100% axes, with bubble size representing current ARR. Muted quadrant backgrounds identify Compounding, Hidden Renewal Risk, Active Decline, and Commercial Mismatch. Standard accounts are blue; hidden-renewal-risk accounts are red. Hidden risk includes usage falling while ARR holds and material ARR growth without corresponding usage growth.

### Revenue Story

Historical views appear only when a Timeline is available:

- **The Portfolio Current:** total ARR and historical signal health share one date axis, with ARR on the left, health on the right, and health-band blocks behind both. Historical signal health is based only on fields available monthly: ARR momentum, utilisation, active-user rate, and tickets.
- **The Revenue Current:** decomposes each month into new ARR, expansion, contraction, churn, and net movement.
- **The Growth Engines:** competing, non-stacked ARR lines default to industry, with segment as a toggle. The five largest groups are shown separately and the remainder are grouped as Other.

Historical signal health is not a reconstruction of past QBR, payment, or contract state. Those monthly snapshots do not exist.

### CEO and CSM question coverage

| CEO question | Product answer |
|---|---|
| What is current recurring revenue? | Current ARR |
| Is ARR growing or shrinking? | 12-month ARR change and The Portfolio Current |
| How healthy is the revenue base? | Portfolio health, band strip, and Portfolio Current |
| How much ARR is exposed? | Critical plus Watch ARR and Health Footprint |
| What requires renewal work? | Immediate Renewals, planning window, and Renewal Horizon |
| Are we dependent on large customers? | Top-five concentration, Value Ladder, and Revenue Skyline |
| How entrenched is the base? | Five-year customer ARR and Customer Roots |
| Which industries combine value and weakness? | Sector Weather and Growth Engines |
| What caused ARR movement? | Revenue Current |
| Are customer signals weakening before ARR? | Portfolio Current and Early-Warning Map |

| CSM question | Product answer |
|---|---|
| Which customers should I act on first? | Intervention Queue |
| Why is each customer unhealthy? | Driver chips and selected scoring explainer |
| Which accounts renew within six or eighteen months? | Renewal Horizon and queue runway |
| Which valuable accounts lack a recent QBR? | Executive Contact Gap |
| Which renewals lack executive engagement? | QBR scatter coloured by runway |
| Which customers are gaining or losing most ARR? | Commercial Tides |
| Which customers are quietly disengaging? | Early-Warning Map |
| How healthy is the active portfolio? | Health Footprint |
| Which scores rely on incomplete data? | Completeness and missing-QBR treatment |
| Does condition agree with revenue direction? | Portfolio Current |

### Shared scoring outputs

Every scoring model produces a value from 0 to 100:

- **Critical:** score at or below 50;
- **Watch:** score above 50 and at or below 75; and
- **Healthy:** score above 75.

There is no separate risk score. Low health means high risk. Portfolio health is ARR-weighted:

\[
H_{portfolio}=\frac{\sum_i ARR_iH_i}{\sum_i ARR_i}
\]

This makes a large account more influential at portfolio level without letting ARR size improve the account's own health score.

### Plain Pulse

Plain Pulse is the default and most basic model. It is exactly reproducible as:

\[
H=\operatorname{clip}(100-D+P,0,100)
\]

The deduction term adds:

- 20 when effective QBR age exceeds 180 days;
- 20 for overdue payment;
- 10 when seat utilisation is below 50%;
- 10 when active-user rate is below 40%;
- 15 for a contract term of 12 months or less, otherwise 5 for 24 months or less; and
- 10 when renewal is within 183 days.

The positive term adds:

- 2 for a recorded QBR no more than 180 days old;
- 2 for utilisation of at least 80%;
- 2 for active-user rate of at least 70%; and
- a mutually exclusive 2, 5, or 8 for at least one, three, or five years of tenure.

A missing QBR inherits customer tenure as its effective age. Ticket volume, segment, ARR trend, ARR expansion, and interaction effects are excluded. Plain Pulse is intended to be hand-calculable and easy to challenge.

### Signal Compass

Signal Compass is the intermediate contextual model:

\[
H=\operatorname{clip}(100-Dm_rm_tm_a+P,0,100)
\]

The deduction term \(D\) contains continuous penalties:

- QBR age ramps from 0 to 25 between 90 and 365 days for Enterprise, 120 and 365 for Mid-Market, and 180 and 540 for SMB.
- Twelve-month tickets ramp from 0 to 15 between 4 and 25 for Enterprise, 2 and 18 for Mid-Market, and 1 and 12 for SMB. The result is multiplied by \(1+0.5p\), where \(p\) is the high-priority-ticket fraction.
- Overdue payment contributes 20.
- Utilisation contributes 0 at 70% and reaches 15 at 20%, linearly between.
- Active-user rate contributes 0 at 60% and reaches 10 at 15%, linearly between.
- A term of 12 months or less contributes 15. A term of 24 months or less contributes 6 unless it is the initial contract starting within 45 days of `customer_since`.

Context multipliers compound:

- \(m_r=1.25\) inside 183 renewal days, 1.10 inside 548 days, otherwise 1;
- \(m_t=1.15\) for tenure below 180 days, otherwise 1; and
- \(m_a=1.15\) when ARR trend is below -5%, otherwise 1.

Positive evidence adds 2 for a recorded QBR at or below the segment clean threshold, 2 for utilisation at least 80%, 2 for active-user rate at least 70%, and 2, 5, or 8 at one, three, or five years. ARR growth and low ticket volume are neutral. Completeness is the observed fraction of QBR, payment, tickets, utilisation, active-user rate, and contract term. An inferred QBR is scored but not counted as observed.

### Retention Horizon

Retention Horizon is the most complex current model and uses a fixed-coefficient logistic form:

\[
H=\frac{100}{1+e^{-z}}
\]

\[
\begin{aligned}
z={}&0.40+1.10\operatorname{clip}(T/1825,0,1)\\
&+0.70[1-2\operatorname{clip}(Q/365,0,1)]\\
&+0.80\operatorname{clip}[(U-50)/50,-1,1]\\
&+0.70\operatorname{clip}[(A-40)/40,-1,1]\\
&+0.55\operatorname{clip}[(L-24)/12,-1,1]\\
&+0.45[2\operatorname{clip}(R/1095,0,1)-1]\\
&-1.20I_o-0.45\operatorname{clip}[(K-K_c)/(K_b-K_c),0,1]\\
&-0.55I_g\operatorname{clip}(|G|/30,0,1)
\end{aligned}
\]

\(T\) is tenure days; \(Q\) is effective QBR age; \(U\) is utilisation; \(A\) is active-user rate; \(L\) is contract months; \(R\) is renewal runway days; \(I_o\) indicates overdue payment; \(K\) is ticket volume; \(K_c\) and \(K_b\) are segment clean and bad thresholds; \(G\) is ARR trend; and \(I_g=1\) only for negative ARR trend. Missing features contribute nothing except a missing QBR with known tenure, which uses tenure as its effective age.

Displayed driver and strength values equal signed linear contributions multiplied by 10, but do not enter the calculation again. The logistic output is not a posterior probability or calibrated survival estimate. Coefficients are design assumptions because the data contain no labelled renewal, churn, contraction, expansion, or value-realisation outcomes.

### Data contract

Snapshot fields include `account_id`, `account_name`, `segment`, `industry`, `csm_owner`, `customer_since`, `contract_start`, `renewal_date`, `term_length_months`, `auto_renew`, `current_arr`, `last_qbr_date`, and available health signals. Legacy monthly-revenue fields remain accepted temporarily and are converted internally, but the product displays ARR only.

Timeline fields are `account_id`, `month`, `arr`, and optional utilisation, active-user rate, and tickets opened. Timeline ARR is the historical source of truth when supplied.

### QBR and contract policy

`customer_since` is required. `last_qbr_date` is optional. A blank QBR means no QBR has ever been recorded; effective QBR age becomes full tenure, the account remains visible, Never Recorded is shown, and completeness falls.

Three years is the standard contract. One-year terms are an explicit negative signal. Two-year terms are acceptable for new customers and weaker for established renewals. Five-year terms increase secured value but do not automatically create perfect health.

### Deterministic sample portfolio

The sample contains 50 historical account records and 46 active positive-ARR accounts. It is fixed at $5.0 million current ARR with 30% top-five concentration. It contains two five-year contracts, a majority of three-year terms, a minority of one-year at-risk terms, two-year terms concentrated among new customers, four blank QBR dates, customers above five years tenure, all runway buckets, and explicit churn, contraction, growth, and silent-decliner narratives. Sterling Capital is the large Enterprise five-year customer. Harbor Advisory is a Mid-Market account whose secured value materially exceeds its ARR rank.

### Verification and limitations

The implementation has automated coverage for scoring, parsing, sample downloads, dashboard contexts, and rendering. It has also received live browser inspection, chart-toggle testing, syntax checks, and overflow review. At the 4 August 2026 review, the full Django suite contained 78 passing tests.

Known limits:

- Historical QBR, overdue-payment, contract-state, and ticket-severity snapshots do not exist, so historical full-health replay would create false precision.
- Retention Horizon has not been fitted or calibrated.
- Direct business outcomes and stakeholder strength are absent from the CSV.
- There is no intervention log, override audit, CRM integration, cohort calibration, or saved history.
- PDF export was specified in an earlier build document but was not implemented; browser print remains available.

### Roadmap summary

The planned evidence step is a versioned monthly account snapshot and labelled outcome history so the transparent models can be tested against renewal, churn, contraction, expansion, and intervention outcomes. CRM integration and saved customer history remain parked until privacy, ownership, retention, and deletion are designed. See Parts 3 and 4.

## 2.6 Life Compass

| Field | Current value |
|---|---|
| Status | Mature private tool with public demonstration mode |
| Introduced | 7 July 2026, unreleased after `2.7.3` |
| Last materially changed | 30 July 2026 |
| Public route | `/life-compass/` |
| Application | `life_compass`; editable frontend source in `personal_dashboard` |
| Data operation | No routine content upload; frontend builds use the cross-repository procedure in `docs/DEPLOYMENT.md` |
| Roadmap references | `LC-P01`, `LC-I01` |

### Purpose

Life Compass is a personal strategy and execution system. It connects long-term direction, current priorities, projects, daily tasks, and evidence of completion. In portfolio terms it demonstrates a more stateful product, private authentication, external frontend build integration, and iterative interaction design.

### Project thesis

Long-term direction is more useful when it is translated into a small set of current projects and daily actions, while completion evidence remains earned, private, and reviewable rather than becoming another performative productivity score.

### Original MVP

The 7 July 2026 MVP brought a TypeScript/Vite application into Django as compiled assets. It provided Home, Strategy, and Execution pages with public demonstration data. Authentication and persistence followed on 8 July.

### Current state

Public mode displays generic demo data. Private mode uses Django session authentication and a `LifeCompassData` record containing one JSON document per user. Browser state is mirrored through `localStorage` and synchronised after meaningful changes. Automated tests cover user isolation.

Strategy includes North Star, Career Compass, Operating Principles, Career Story, Long-Term Direction, and Current Season. Execution includes three daily tasks derived from project subtasks, a weekly focus, a project kanban, an earned completion calendar, a Done Ledger, archive/restore behavior, and an untracked focus timer.

The visual identity uses parchment, navy, brass, cartographic dividers, inline compass SVGs, and a bounded bireme image in the hero. The full-page background is intentionally parked rather than declared final.

### Product evolution

| Site release | Date | Change | Product rationale |
|---|---|---|---|
| `Candidate 2.8.0` |  7 Jul 2026 | Initial app and navigation integration | Add a personal strategy product and public demo |
| `Candidate 2.8.0` |  8 Jul 2026 | Authentication and per-user JSON persistence | Make the tool privately usable without redesigning its frontend model |
| `Candidate 2.8.0` |  13 Jul 2026 | Phases 1 to 3 | Remove duplicate controls, fix ledger duplication, create lifecycle colours, derive daily tasks from projects, and make calendar marks earned |
| `Candidate 2.8.0` |  14 Jul 2026 | Historical-navigation visual redesign | Align the interface with its navigation metaphor |
| `Candidate 2.8.0` |  30 Jul 2026 | Execution overhaul and follow-up | Add archive, aging, undo/reset correctness, project and task ledger views, focus prompt, X Calendar redesign, and Pomodoro overlay |

### Source and build boundary

The editable frontend source lives in `personal_dashboard`, not in this Django repository. This repository contains compiled hashed assets, Django template shells, authentication, and persistence. The safe production build and asset-copy procedure is operational and lives only in `docs/DEPLOYMENT.md`.

Any new full-panel overlay must use a real element. Existing cartouche styling already occupies panel pseudo-elements, so attempting to reuse `::before` or `::after` can silently lose layout properties.

### Dated design rationale

The X Calendar moved through several concepts on 30 July 2026. Multiple marks per day were rejected as busy; one mark per day became the invariant. A red severity ramp became a gold-on-silver reward language, then a red-starting, gold-ending ramp. The project-completion seal evolved from generic heraldry to the app's own compass rose. Today's cell retained a simple pulsing brass ring. Kanban aging deliberately uses black through orange to red so warning colour does not collide with the calendar's reward language.

The background went through CSS textures, procedural SVG watermarks, and a supplied photographic illustration. A full-screen fixed-resolution image became blurry when enlarged and letterboxed when contained. The bounded hero treatment avoids both problems. The current graticule and corner compass remain acceptable but parked.

### Known boundaries

- Build integration between the source repository and Django is manual.
- The background direction is unresolved but not blocking.
- Accessibility has not received a formal audit after the major visual work.
- The July dependency cleanup identified vulnerable versions that require a separate, tested upgrade pass.

### Roadmap summary

The planned engineering step is a safe, reproducible build-and-copy command that eliminates manual template hash changes. A full-page background redesign remains parked until a better source or technique exists. See Parts 3 and 4.

---

## 2.7 World Ledger

| Field | Current value |
|---|---|
| Status | Functional Giga Dataset v1.0 data-story product |
| Introduced | 6 August 2026, unreleased after `2.7.3` |
| Last materially changed | 6 August 2026 |
| Public route | `/world-ledger/` |
| Application | `world_lens` |
| Data operation | Reviewed dataset generation; see `docs/DEPLOYMENT.md` |
| Roadmap references | `WORLD-P01`, `WORLD-I01`, `WORLD-I02` |

### Purpose

World Ledger lets readers compare present economic power and the structural conditions for future power while making the assumptions and weights behind any ranking visible.

### Project thesis

World Ledger is a comparative strategy map of economic power. Its central claim is that no ranking of power is neutral: changing the importance assigned to markets, industry, trade, finance, population, institutions, demographics or resources produces a different ordering of the world. That exposes the theory of power embedded in the result.

Power Now shows where economic power sits today. It measures observable weight across domestic markets, productive capacity, trade reach, financial buffers and population, revealing both the scale of an economy and the structures through which that scale can be mobilised.

Power Potential shows where the conditions for greater economic power already exist. It measures observed momentum, reinvestment, demographic runway, conversion capacity, productive depth, macroeconomic resilience and resource optionality, revealing economies with the capacity to strengthen their position and those whose present power rests on weaker foundations.

### Original MVP

The 6 August 2026 MVP established a database-free comparative dashboard, one complete-data 48-economy cohort, separate Power Now and Power Potential models, adjustable pillar weights, signed contribution ledgers, and six linked SVG stories. It deliberately preferred one defensible fixed cohort and transparent composite arithmetic over broader coverage obtained through imputation.

### Current state

### Product contract

World Ledger must make a theory of economic power visible and adjustable. It has three essential outputs:

1. a rank across one fixed, defensible comparison cohort;
2. a signed decomposition showing which pillars raise or lower each score; and
3. linked visual stories that reveal distribution, divergence, trade relationships, conversion capacity and surprising rank differences.

The primary interaction is changing the importance of each pillar from zero to twice its neutral weight and seeing the entire cohort reorder. Power Now and Power Potential remain separate constructs with separate controls, but they share one comparison cohort and can be compared through rank and position.

### Giga Dataset version 1.0

The 6 August 2026 build uses one fixed cohort of 48 economies with complete coverage across both models. Inclusion occurs in two stages:

1. require a valid observation for every scored Giga v1 input; then
2. order the complete-data pool under equal-weight Power Now and admit the first 48 economies.

China and India are included by this rule rather than by manual exception. The same 48-economy denominator is used by both ranking models and all six visual stories. Missing observations are not imputed. The current selectable cohort is:

- **East Asia and Pacific:** Australia, China, Indonesia, Japan, Malaysia, Philippines, Singapore, South Korea, Thailand and Vietnam.
- **Europe and Central Asia:** Austria, Belgium, Czechia, Denmark, France, Germany, Ireland, Italy, Kazakhstan, Netherlands, Norway, Poland, Romania, Russia, Spain, Sweden, Switzerland, Turkiye, Ukraine, United Kingdom and Uzbekistan.
- **Latin America and Caribbean:** Argentina, Brazil, Colombia, Mexico and Peru.
- **Middle East, North Africa, Afghanistan and Pakistan:** Algeria, Egypt, Iraq, Israel, Morocco, Pakistan and Saudi Arabia.
- **North America:** Canada and the United States.
- **South Asia:** Bangladesh and India.
- **Sub-Saharan Africa:** South Africa.

The interface uses World Bank display names and regions. The document uses familiar short names where doing so does not alter the entity.

### Scoring architecture

Each model follows the same transparent calculation:

1. transform absolute scale observations with `log10`; resource values that may be zero use `log1p`;
2. standardise each observation as a z-score across the fixed 48-economy cohort;
3. reverse observations where a lower raw value represents greater strength, currently inflation and growth volatility;
4. average exactly three observation z-scores into one pillar z-score;
5. normalise the active pillar weights to sum to one;
6. sum the weighted pillar contributions; and
7. rank all 48 economies from highest to lowest composite score.

In compact notation, observation `j` for economy `c` becomes `z(c,j)`. Pillar `k` is `P(c,k) = (z1 + z2 + z3) / 3`. For active weights `w(k)`, the model score is `S(c) = sum(w(k) * P(c,k)) / sum(w(k))`. Each signed contribution is the corresponding term in that weighted sum. Scores are cohort-relative standardised composites; they are not quantities of power with physical units.

The neutral baseline assigns every pillar weight 1.00. Weight changes are browser-local, do not mutate the prepared dataset and recalculate the full cohort rather than only the selected economies.

### Pillar dictionary

| Model | Pillar | Three observations | Intended meaning |
|---|---|---|---|
| Power Now | Domestic market | GDP at PPP; household consumption at PPP; GDP at market exchange rates | Internal economic scale, purchasing power and internationally priced weight |
| Power Now | Productive base | Manufacturing value added; industry value added; manufacturing share of GDP | Absolute industrial capacity and its importance inside the economy |
| Power Now | Trade power | Exports; imports; effective number of trade partners | Ability to sell abroad, attract supply and reach a broad partner network |
| Power Now | Financial buffer | International reserves; reserves relative to annual imports; current-account balance | External liquidity and room to absorb pressure |
| Power Now | Population base | Total population; working-age population; urban population | Human scale available to produce, consume and organise |
| Power Potential | Growth momentum | 2015–2024 real GDP growth; latest three-year real growth; 2015–2024 real GDP per-capita growth | Breadth, recency and per-person quality of observed growth |
| Power Potential | Reinvestment | Gross capital formation; gross domestic savings; FDI inflows | Current output being converted into domestic and foreign-financed capital |
| Power Potential | Demographic runway | Working-age share; population aged 0–14; population growth | Present labour capacity, future entrants and demographic momentum |
| Power Potential | Conversion capacity | Government effectiveness; regulatory quality; fixed broadband subscriptions | Institutional and digital systems that turn assets into output |
| Power Potential | Productive depth | Manufacturing share; Economic Complexity Index; effective number of export categories | Industrial intensity, sophistication and breadth of productive capabilities |
| Power Potential | Macro resilience | Inflation; current-account balance; real-growth volatility | Price stability, external balance and steadiness through the cycle |
| Power Potential | Resource optionality | Natural-resource rents; strategic-resource exports; effective number of resource export groups | Currently observable extractive value, trade scale and breadth |

Repeated observations across different models are deliberate where the construct changes. Manufacturing share measures current industrial weight inside Productive Base and a condition for future capability inside Productive Depth. Current-account balance measures present external room inside Financial Buffer and cyclical resilience inside Macro Resilience. Within a single pillar, related measures receive one shared pillar vote rather than independent interface weights.

### Data sources and derived measures

| Source | Grain and period | World Ledger use |
|---|---|---|
| World Development Indicators | Country-year, primarily 2015–2024 | Market scale, industry, reserves, growth, investment, savings, FDI, demographics, broadband, inflation, current account and resource rents |
| Worldwide Governance Indicators | Country-year, 2015–2024 | Government effectiveness and regulatory quality |
| Harvard Growth Lab Atlas of Economic Complexity | Country-year, bilateral country-pair and two-digit product, 2024 | Exports, imports, ECI, trade-partner breadth, export-category breadth, resource exports and six largest export destinations |

Latest-value observations must be from 2020 or later. Historical averages require at least five observations and normally use 2015–2024. The latest three-year growth measure uses the three most recent valid annual observations. Growth volatility is the population standard deviation of observed annual real growth over the scoring window.

Effective partner and product counts use the inverse Herfindahl index, `1 / sum(share²)`, so a diversified network is expressed as the equivalent number of equally sized partners or categories. Working-age population is total population multiplied by the working-age share. Reserve import coverage is international reserves divided by annual Atlas imports.

Strategic-resource exports are restricted to HS chapters 25, 26, 27, 44 and 71: minerals, ores, fuels, wood, precious metals and stones. Atlas service categories are excluded from this calculation. This is an explicit extractive-trade definition rather than an attempt to classify every biological or manufactured commodity as a resource.

### Interface and visual stories

The global controls contain two model buttons, one country selector supporting up to three economies, removable selected-economy chips and one slider per active pillar. Country options show both economy and World Bank region.

1. **Weighted ranking:** the leaderboard and signed contribution chart display the same dynamically sorted top ten. Selected economies outside the top ten are appended below it while retaining their true rank. Selected rows receive a terracotta accent. Changing weights reorders both sides together.
2. **Ranking histogram:** ten equal-width score bins show the distribution across all 48 economies. Selected economies are marked above their bins.
3. **Power map:** every economy appears with Power Now on the horizontal axis and Power Potential on the vertical axis. Bubble area represents GDP at PPP; colour represents region; selected economies receive labels and stronger outlines.
4. **Surprise index:** the five largest positive and five largest negative gaps between GDP-at-PPP rank and the active model rank are shown. Selected countries are not inserted unless they naturally qualify as an extreme.
5. **Trade constellation:** each selected economy connects to its six largest 2024 export destinations. Destination, export share and export value are printed on every route; line width also represents share.
6. **Conversion bridge:** four asset pillars, growth momentum, reinvestment, demographic runway and resource optionality, are averaged separately from three conversion pillars, conversion capacity, productive depth and macro resilience. Each selected economy shows both group z-scores and its resulting Power Potential and Power Now ranks. The bridge is diagnostic arithmetic, not a causal model.

The Evidence Ledger follows the same selected economy set. Each pillar header shows the pillar z-score for every selected economy, followed by exactly three raw observation rows with unit, reporting period, observation count, source and observation z-score. Pillar headers use a coloured left rule and shaded background so they cannot be mistaken for missing data.

### Data build and runtime architecture

`world_lens/management/commands/refresh_world_lens_data.py` downloads, validates, derives and scores the dataset. It writes the versioned artifact to `world_lens/data/world_lens.json`. The Django view reads that artifact and embeds it with Django's `json_script`; no request-time external API call, database table or server-side scoring is required.

The public route is `/world-ledger/`. The earlier `/world-lens/` path is retained as a permanent redirect. The Django package remains named `world_lens` to avoid a cosmetic code migration. The main implementation files are:

- `world_lens/views.py` for prepared-data loading and template context;
- `world_lens/templates/world_lens/dashboard.html` for thesis, controls, visual-story structure, evidence ledger and method copy;
- `world_lens/static/world_lens/js/world_lens.js` for local state, reweighting, reranking and SVG rendering;
- `world_lens/static/world_lens/css/world_lens.css` for the editorial layout and responsive chart system;
- `world_lens/management/commands/refresh_world_lens_data.py` for source ingestion, cohort selection and scoring; and
- `world_lens/data/world_lens.json` for the generated client-side artifact.

The browser stores only transient selection and weight state. JavaScript recalculates rankings and renders all SVG charts locally. A data refresh is therefore a reviewed build step rather than a live dependency:

1. run `python manage.py refresh_world_lens_data` with network access;
2. confirm that at least 48 economies retain complete coverage and that China and India pass the rule;
3. review cohort changes, source update dates, outliers, reversed directions and derived values;
4. run the World Ledger tests, JavaScript syntax check and full Django suite;
5. browser-check both models, weight changes, selected-country append behaviour, every visual and mobile overflow; and
6. commit the generated JSON together with the builder and documentation changes.

### Product evolution

| Site release | Date | Change | Product rationale |
|---|---|---|---|
| `Candidate 2.8.0` |  4 Aug 2026 | Initial comparative-country dashboard prototype | Test whether a transparent, adjustable composite could support a Data Stories product |
| `Candidate 2.8.0` |  6 Aug 2026 | Renamed the product World Ledger and locked the Power Now / Power Potential thesis | Move from a generic development dashboard to a focused strategy map of economic power |
| `Candidate 2.8.0` |  6 Aug 2026 | Introduced one complete-data 48-economy Giga v1 cohort | Make ranks directly comparable and include China and India by rule rather than exception |
| `Candidate 2.8.0` |  6 Aug 2026 | Added Harvard ECI, bilateral trade and product structure | Represent trade reach, network breadth, productive complexity and resource exports |
| `Candidate 2.8.0` |  6 Aug 2026 | Expanded every pillar to exactly three observations | Make the evidence ledger analytically rich while containing correlated metrics inside pillars |
| `Candidate 2.8.0` |  6 Aug 2026 | Aligned leaderboard and contribution rows and clarified surprise, trade and conversion views | Ensure every visual answers an explicit question and selected countries remain traceable |

### Analytical boundaries

- Power Now and Power Potential use the same fixed 48-economy cohort. Their ranks can be compared, but their score values describe different constructs.
- The cohort is earned through complete coverage and baseline materiality. It is not a hand-picked list of preferred countries.
- Population is strategic scale, not prosperity. Government effectiveness is perception-based. Strategic-resource exports cover HS chapters 25, 26, 27, 44 and 71. Resource rents and exports show current extraction and trade, not reserves, ownership or sovereign control. These meanings must remain visible.
- The current country list follows the World Bank economy registry. A sovereign-state and historical-boundary crosswalk is required before describing every row as a country.
- Weight changes are browser-local, normalised and applied to the entire cohort. They create scenarios, not new official models.
- The default scores are descriptive and cohort-relative. They are not probabilities, forecasts or claims about national quality.
- No forecast or expert projection may enter Power Potential. Historical averages and present structural observations are permitted.
- Data refresh is manual and must be reviewed before the generated JSON is committed.

### Roadmap summary

The planned evidence work is coverage confidence and rank-robustness analysis. Further statistical stories and dataset layers, including demographics, industrial depth, electricity, finance, ownership, logistics, historical velocity, and transparent shock scenarios, remain in the idea phase until coverage and interpretation rules are scoped. See Part 3.

### Verification

The app has database-free rendering and schema tests and keeps its prepared dataset client-side. Automated World Ledger tests verify the route, embedded dataset, exact 48-economy cohort, China and India inclusion, three observations per pillar, both model payloads, removal of synthetic trade-partner aggregates and the legacy redirect.

The 6 August 2026 verification included:

- `node --check` for the dashboard JavaScript;
- `manage.py check` with no system-check issues;
- five passing World Ledger tests and 147 passing tests across the full repository;
- six rendered SVG stories with no browser console warnings or errors;
- matched top-ten leaderboard and contribution rows;
- a selected Malaysia row appended outside the top ten while preserving its true rank;
- a conversion-capacity-only scenario that moved Switzerland to the top of Power Potential, confirming live rank reordering;
- 15 Power Now evidence rows and 21 Power Potential evidence rows beneath clearly populated pillar headers; and
- desktop and 375-pixel mobile review with no page or chart overflow.

A formal accessibility audit remains future work. Each SVG currently has an accessible name, but the charts still need equivalent non-visual data summaries, keyboard review beyond the weighted contribution segments, colour-contrast measurement and reduced-motion confirmation.

---

## 2.8 East Coast Gas System Stress Monitor

| Field | Current value |
|---|---|
| Status | MVP, stages one to four of six complete |
| Introduced | 10 August 2026, unreleased after `2.7.3` |
| Last materially changed | 10 August 2026 |
| Public route | `/nem/flow-trace/` (`/gas/` redirects permanently) |
| Application | `gas_monitor` |
| Data operation | One-time archive backfill plus daily time-series refresh and Monday reference refresh; see `docs/DEPLOYMENT.md` |
| Roadmap references | `NEM-S01`, `GAS-P01`, `GAS-P02` |

### Purpose

Explain how production, pipelines, storage, demand, gas-powered generation and hub prices interact across Australia's east coast gas system: where gas is moving, when the system is becoming constrained, and which physical conditions contribute to a market stress event.

### Project thesis

Gas-market stress becomes intelligible when physical supply, transport capacity, linepack adequacy, storage position, end-use demand, and price are presented as one dated system while reporting changes and denominator limitations remain visible rather than being mistaken for market events.

The deeper market thesis is that Australia exports most of its east-coast gas from one end of a connected network while the far end can struggle to meet winter demand. The product measures that contradiction from the operator's own data. Its transferable question is: when a physical network is optimised around export, what does the domestic remainder cost, and where does the constraint fall?

### Original MVP

The first four-stage MVP built the static east-coast system model, thirty-day current flow and outlook ingestion, full-history flow and linepack backfills, a constraint strip, demand composition, pipeline utilisation, and like-for-like seasonal storage context. Prices, the network schematic, and a combined stress decomposition were deliberately left unbuilt and labelled as such.

### Current state (10 August 2026)

**Stage one, the static system model**, ingested from the AEMO Gas Bulletin Board reference reports:

| | Count |
|---|---|
| Facilities | 157 — 45 pipelines, 42 production, 42 gas-powered generators, 10 large users, 7 storage, 7 compression, 3 LNG export, 1 blended distribution |
| Locations | 25, of which 4 are trading hubs |
| Connection points | 768, 325 mapped to a demand zone |
| Rated capacity legs | 195, effective-dated |
| Basins / linepack zones | 15 / 55 |

**Stage two, the physical time series.** 30 gas days of actual flows and storage (5,838 rows), 7 days of forward nominations, 3 days of forward linepack adequacy flags, a year of recorded non-submissions, and per-source coverage tracking. The page shows the most recent gas day's end-use demand split, storage positions with injection and withdrawal direction, the forward constraint outlook and a data-currency table.

**Stage three, history and the first two charts.** Backfilled from the full-history archives: **432,121 flow rows across 2,872 gas days (29 September 2018 to 9 August 2026, no gaps)** and **109,798 linepack adequacy flags across 3,196 gas days**, the latter reaching to June 2027 because outlooks are forward-published. Two hand-built SVG charts: a constraint strip and a stacked demand composition.

**Stage four, utilisation and storage context.** Pipeline throughput against effective-dated capacity, and storage measured against its own seasonal history. Backfilled the nameplate archive (124,191 ratings back to April 2019) and added a third chart.

**Prices, the system schematic and the stress components are specified but not built**, and the page says so rather than implying otherwise.

### Utilisation, and what it can honestly claim

**Throughput is receipts, not deliveries** — `supply + transfer_in` — because that is the quantity a rating constrains. Deliveries differ by fuel burn and linepack movement.

**A correction from stage two:** the model previously documented a pipeline's `demand` as gas received for transport. That is backwards. Measured against MSP on 9 August 2026, `demand` is gas **delivered out** to consumers at that location (Sydney 127.4, Regional NSW 39.8, ACT 19.2), while receipts arrive as `transfer_in` (Moomba Hub 180.1, Culcairn 30.3). The double-counting conclusion was right; the stated reason was wrong.

**The nameplate archive is mandatory, not a nicety.** `GasBBNameplateRatingCurrent.csv` holds only what is in force *now*, and on 10 August 2026 every Moomba to Sydney rating carried an effective date of 2026-08-10 — so gas day 2026-08-09 had **no rating in force at all** from the current file. Without `GasBBNameplateRating.zip`, "the rating in force on that gas day" is a phrase rather than a lookup.

**Capacity is the largest leg in force, never the sum.** Legs are alternative receipt-to-delivery paths and a bidirectional pipeline publishes one each way; adding them invents capacity that cannot exist at once. Per-leg utilisation is not derivable at all, because flows are reported per location rather than per leg.

**The known limit of the measure, stated on the page.** Maximum daily quantity is a *point-to-point* rating, so a pipeline taking gas in at several points can legitimately carry more than any single leg allows. The South West Queensland Pipeline received 474.5 TJ at Wallumbilla and 161.5 TJ at Moomba on 9 August 2026 — 636 TJ against legs of 512 and 340, computing to 124%. That is the denominator failing to describe the pipeline, not scarcity. Such pipelines are flagged `denominator_suspect`, drawn with a hatched meter, and **excluded from the count above 90%**, because counting them would manufacture tightness out of a modelling limitation. On that gas day: 1 of 42 meaningful pipelines above 90% (Wallumbilla to Gladstone at 94.7%), with 2 suspect.

The page also states that this is our own arithmetic, not an AEMO measure — AEMO's own view is the linepack adequacy flag, which carries more authority than any percentage computed after the fact.

### Storage, and the comparison that was contaminated

A holding only means something next to what is usually held at that point in the season, so each facility is drawn against **the median for the same day-of-year in other years**, excluding the year being drawn so a line is never compared against itself.

**The trap, found and fixed:** the first implementation summed the system first and compared totals across years. Silver Springs reported on 9 August in every year from 2021 to 2025 but not in 2026, so a five-facility total was being measured against six-facility history and showed a **39% shortfall that was pure artefact**. The reference is now built per facility and summed only over facilities reporting that day; the like-for-like figure is 23% below median, and the page names who is absent.

That fix also revealed the finding the aggregate was hiding — a regional divergence, not a system-wide drawdown:

| Facility | Held (TJ) | Median for the day | |
|---|---|---|---|
| Roma Underground Storage | 15,157 | 24,598 | 62% |
| Moomba LDB | 6,306 | 10,862 | 58% |
| **Iona Underground** | **14,403** | **11,487** | **125%** |
| Newcastle Gas Storage | 678 | 488 | 139% |
| Dandenong LNG | 612 | 579 | 106% |
| Silver Springs | not reported | 13,359 | — |

Queensland storage is drawn well down while Victorian and NSW storage sit above their seasonal norms. A single system total reports "77% of median" and loses the entire story.

### The 15 March 2023 discontinuity

The single most dangerous fact in the historical record, found during the backfill and encoded as `GBB_EXPANSION_DATE`.

Before that date the flow record contains **only pipelines, production, storage and compression** — 88 reporting facilities. On that date LNG export, large users and gas-powered generation begin reporting, taking it to 141, and 154 today.

| Type | First gas day in the record |
|---|---|
| `PIPE`, `PROD`, `STOR` | 29 September 2018 |
| `COMPRESSOR` | 1 February 2019 |
| `LNGEXPORT`, `BBLARGE`, `BBGPG` | **15 March 2023** |

An end-use demand chart drawn across that boundary shows demand rising out of literally nothing in March 2023 — a reporting change wearing the costume of a market event. `demand_composition()` therefore clamps its start to the expansion date whatever window is requested, and returns a `truncated` flag so the page states why. Pipeline, production and storage series are safe back to 2018 and should use the full record.

This also constrains step 6: **the June 2022 event cannot be replayed on the demand side at all.** Only pipelines, production and storage existed in the record then. Either the validation event moves to a post-2023 one, or the case study is explicit that it reconstructs supply and transport only.

### Visualisation

The original visual brief is retained as the [East Coast Gas System Stress Monitor concept](images/east-coast-gas-system-stress-monitor-concept.png). It is design evidence, not a claim that every pictured component is implemented.

**Hand-built SVG, no charting library**, diverging from `nem_dashboard` and `nem_price_lab` which both use Chart.js. §1.3 permits divergence that expresses the product, and four reasons apply specifically here:

1. Two of the four planned visuals are a heatmap grid and a network schematic. Chart.js draws neither without plugins, so a library would leave two rendering models on one page.
2. The data is daily — a year is 365 points, so the performance case for canvas does not arise.
3. Colours come from CSS custom properties, so **dark mode works by inheritance**. Verified: the constraint cell moves from `#b84a1a` to `#d4693a` on theme toggle with no JavaScript redraw. A canvas chart has to re-read tokens and repaint.
4. Real DOM nodes carry `<title>` and aria; canvas cannot, and the Part 1 definition of done requires chart alternatives.

The cost is hand-written scales, ticks and tooltips, shared by one helper in `gas_monitor.js`. `world_lens.js` already established the pattern in-repo.

**Identity: terracotta is reserved exclusively for constraint.** It never appears decoratively on this page — when it appears, something is tight. Demand bands therefore use ink and sage tones only, so the one alarm colour keeps its meaning. Flagged cells are also drawn taller than adequate ones, so the strip survives a monochrome print and a colour-vision difference, satisfying §1.4 principle 9 without a second legend.

**Constraint strip.** One cell per pipeline per gas day, 180 days. Only pipelines flagged at least once are drawn — 53 rows of unbroken green buries the signal in its own background. A summary band counts flagged pipelines per day.

**Chronic versus episodic.** The strip immediately surfaced something a single-day view hides: Comet Ridge to Wallumbilla and GLNG Gas Transmission — both Curtis Island feed lines — were flagged on **179 of 180 gas days**, while Queensland Gas Pipeline and VicHub were flagged twice and once. Those are different phenomena. A pipeline flagged on two thirds or more of its assessed days is labelled *chronic* and the rest *episodic*, with the raw count shown alongside so a reader can disagree with the threshold. Presenting them identically would turn a permanent structural condition into an alarm that never stops, which is how a monitor loses its reader.

**Demand composition.** Stacked area, 365 days, LNG export / large users / generation. LNG is drawn as the stable mass it is; generation is the thin volatile band. Pipelines are excluded because their reported demand is transport, not consumption.

### Data acquisition

Source is `nemweb.com.au/Reports/Current/GBB/` — unauthenticated HTTP GETs, stdlib `urllib` only, no new dependency. Three ways in, deliberately ranked:

1. **`manage.py ingest_gbb_reference`** — the real path, schedulable as-is. Accepts `--report` to refresh one file and `--file` to replay a local copy when the network is the problem.
2. **Admin → Gas data refreshes** — creates a `GasDataRefresh` row whose `post_save` fetches and writes the import summary back onto the row, mirroring the fuel-mix upload's affordance. Measured at 0.6 s for all seven reference reports, comfortably inside the request timeout. **Deliberately not a file upload:** the server can fetch these itself, so asking an operator to download and upload twenty files a day would invent manual work the Price Predictor Lab already declined to invent.
3. **SSH** — backfill and archive recovery only. A dozen sequential fetches will outlast the gunicorn timeout, so backfill must never run behind a Save button.

### Design decisions

- **The natural key is `(gas day, facility, location)`, not `(gas day, facility)`.** A facility reports at every location it touches: on gas day 6 August 2026 the Victorian Transmission System reported at nine locations, MSP and EGP at five each, giving 194 rows across 153 facilities. The shorter key silently discards 21% of the rows with no error. Recorded on `ConnectionPoint` because the flow tables will inherit it.
- **Capacity is effective-dated and multi-leg.** Utilisation must be measured against the rating in force on the day shown, not today's rating. Bidirectional pipelines publish two rows — the Port Campbell Interconnect carries a separate 400 TJ leg each way — which is the only way reverse-haul capability is discoverable. 22 pipelines currently hold more than one rated leg, so capacity is never reduced to one number per pipeline.
- **Demand must not be summed across facility types.** Pipelines report "demand" as gas received for transport. On 6 August 2026 the WGP pipeline and the QCLNG plant each reported 1,517.150 TJ — one quantity of gas counted twice. `END_USE_TYPES` exists to make the correct denominator explicit.
- **Bulletin Board ids are the primary keys.** They are stable, they are how the flow reports will join back, and using them means an upsert cannot create a second row for the same facility.
- **Orphans are reported, not dropped.** A connection point whose facility is not held, or a nameplate leg for an unregistered facility, is counted and surfaced. Five nameplate legs currently reference facilities absent from the registry; that is information about registry lag, not noise.
- **Tolerant date parsing.** One directory serves `2023/05/25`, `2019/08/29 16:17:08` and `29 Aug 2019 00:00:00`, sometimes in different columns of one file. Guessing a single format would drop rows silently.
- **Revisions resolve newer-wins, not last-writer-wins.** Every flow row carries the source's `LastUpdated`, and an incoming row is discarded when the stored one is newer. That makes ingestion order-independent, so an archive backfill running after an incremental cannot undo it. Rows never seen, and rows where either timestamp is unknown, are always written — "unknown" is not evidence of being newer, and refusing to write would strand the record permanently. The reference tables deliberately skip this: they are snapshots of current state, where last-writer-wins is correct.
- **Forecasts live in a separate table from actuals.** The two carry identical columns and one table with a `kind` flag would be less code, but §1.4 principle 3 forbids conflating them and a flag is exactly how they get conflated in a careless query later.
- **The linepack flag's `GasDate` carries a 15:15 time** that is the assessment moment, not part of the gas day's identity. Reducing it to a date preserves one flag per pipeline per day; keeping it would multiply rows on every reassessment.
- **Blank is not zero.** A blank storage holding means "this facility does not store gas" and is stored as null; blank flow columns mean the facility reported and moved nothing that way, and are stored as zero. Most rows are the former — 5,663 of 5,843 in the 31-day window.
- **A forward source is ahead, not negatively behind.** The same subtraction that measures lag for an actuals report measures reach for an outlook, so coverage reports `days_behind` and `days_ahead` as separate fields. Rendering a forecast as "−6 days behind" reads as a bug on the page.

### Data maintainability and operating boundary

The product now participates in the daily 09:00 NEM-suite refresh. Current flows and outlooks update every day; reference data are loaded before time series each Monday so newly registered facilities exist before dependent flows arrive. Source revisions resolve newer-wins, archive and incremental ingestion are idempotent, and coverage checks make missed days visible.

Flows and storage are the binding operating obligation because AEMO's current directory holds approximately 31 gas days. A failed day reduces freshness but does not lose coverage; a failure lasting roughly a month can require archive recovery. Missing-submission history has approximately a year of slack, while nominations and linepack adequacy are forward-looking.

The page exposes data currency and remaining source-window margin. Exact commands, the one-time archive backfill, unified daily scheduler, verification, and missed-window recovery live only in `docs/DEPLOYMENT.md`.

### Product evolution

| Site release | Date | Iteration | Change | Product consequence |
|---|---|---|---|---|
| `Candidate 2.8.0` |  10 Aug 2026 | Stage one | Static Gas Bulletin Board system model and reference ingestion | Established stable facility, location, connection, zone, and effective-capacity identities |
| `Candidate 2.8.0` |  10 Aug 2026 | Stage two | Current flows, storage, forecasts, adequacy, missing submissions, and currency tracking | Made the latest physical state and source freshness visible |
| `Candidate 2.8.0` |  10 Aug 2026 | Stage three | Full-history flow and linepack backfill plus constraint and demand charts | Enabled historical context while exposing the March 2023 reporting break |
| `Candidate 2.8.0` |  10 Aug 2026 | Stage four | Effective-dated utilisation and like-for-like seasonal storage comparison | Prevented false tightness and false storage shortfalls caused by invalid denominators |

### Roadmap summary

The scheduled operating work is the first production archive backfill and activation of the unified daily refresh. Planned product stages add hub prices, a system schematic, and a transparent stress decomposition. Event replay must use a post-March-2023 event for full demand coverage or explicitly limit earlier events to supply and transport. See Part 3.

### Known boundaries

- **Daily resolution.** One value per gas day for flows, storage, constraint flags and STTM prices. Victorian linepack is hourly and the DWGM publishes five daily schedules; nothing else is intra-day.
- **The gas day starts at 06:00 AEST** for the Bulletin Board and the DWGM. The STTM and Gas Supply Hub currently use a different start and an AEMC harmonisation rule change is live, so no view overlays a Bulletin Board flow on an STTM price until that conversion is written and tested.
- **No coordinates are published.** Any future map is a schematic; distances on it are not real.
- **No routed flows.** The Bulletin Board reports facility-level receipts, deliveries and transfers, not "X TJ moved from A to B". A path between two hubs is an inference and must be labelled as one.
- **Coverage is the eastern system plus the Northern Territory**, which the Northern Gas Pipeline connects to Queensland. Western Australia runs a separate Bulletin Board and is out of scope.
- **Quantities are terajoules.** Storage holdings too: Iona held 14,474 TJ on 6 August 2026, which is 14.5 PJ. Reading that figure as PJ overstates it a thousandfold, and Iona is not the largest store — RUGS holds more.

### Verification (10 August 2026)

38 app tests, adding to stage one's coverage: the (gas day, facility, location) fan-out, re-ingest idempotency, a newer revision overwriting, an older row failing to clobber a newer one, blank-storage-is-null, storage withdrawal reading as negative net, orphan flow reporting, the linepack assessment-time reduction, forecasts staying separate from actuals, coverage margin arithmetic, forward-source direction, gap detection, the 2023 demand-series clamp, dense zero-filled bands, chronic-versus-episodic classification, capacity-in-force lookup, largest-leg-never-sum, receipts-not-deliveries, suspect-denominator exclusion, and both storage-reference guards. 231 tests passing repo-wide; `manage.py check` clean; `node --check` on the chart JavaScript; live weekly ingestion of all eleven reports (8,919 rows) with flows re-run and counts unchanged; page rendered against real data with no console errors.

**Corrected during stage four.** A pipeline's `demand` column was documented as gas received for transport; it is gas delivered out to consumers (see above). The first storage seasonal comparison summed the system before comparing years, producing a 39% shortfall that was entirely a coverage artefact.

**Two figures corrected during stage two.** The missing-submission report was assumed to be a 31-day window and actually holds 365 days, which changes the maintenance tolerance in the operator's favour. LNG export's share of end use was stated as "roughly 70%" and is **83.7%** on gas day 6 August 2026 — the error understated the single most important fact about this market.

## 2.9 ChargeTrace: NEM Battery Dispatch and Value Stack Explorer

| Field | Current value |
|---|---|
| Status | Evolving expanded MVP |
| Introduced | 10 August 2026, unreleased after `2.7.3` |
| Last materially changed | 10 August 2026 |
| Public routes | `/nem/charge-trace/` and `/nem/charge-trace/guide/` (former top-level routes redirect) |
| Application | `nem_battery_explorer` |
| Data operation | Registry review plus the unified daily 09:00 refresh; see `docs/DEPLOYMENT.md` |
| Roadmap references | `NEM-S01`, `CT-P01` to `CT-P05` |

### Purpose

ChargeTrace answers five connected questions:

1. What did the selected battery physically do at five-minute resolution?
2. How did its dispatch relate to regional energy and FCAS prices?
3. What public, observable gross market value resulted?
4. How effectively did it use finite stored energy relative to a constrained price-only hindsight benchmark?
5. How is rapid fleet growth changing the market opportunity from which batteries earn?

The product deliberately joins physical dispatch, stored energy, observable value, fleet coverage, and market structure. A dashboard showing dispatch alone answers what happened. ChargeTrace is intended to progress toward why it happened, whether the public opportunity was captured, and whether increasing competition is changing the answer.

### Project thesis

The collapsible thesis appears near the top of the interface so the analytical purpose is visible without taking over the first viewport:

> Batteries are becoming the NEM's marginal intraday balancing technology. They do not create energy; they move it through time, absorb surplus supply, respond to frequency deviations and preserve scarce capacity for periods when the system values flexibility most. As more batteries connect, their collective behaviour increasingly shapes the prices from which they earn revenue.
>
> ChargeTrace tests how that transition appears in public evidence. It reconstructs what selected batteries did at five-minute resolution, estimates the observable value of energy and FCAS enablement, and compares actual operation with a transparent, price-only hindsight benchmark. The purpose is not to estimate participant profit. Private contracts, degradation costs, network obligations, losses and trading intent remain outside the public dataset.
>
> The central commercial question is whether growing battery volume creates more value or competes it away. More capacity can shift more renewable energy, reduce extreme prices and strengthen the grid, while simultaneously compressing arbitrage spreads and ancillary-service prices. ChargeTrace therefore treats dispatch, stored energy, market value and fleet growth as one connected story. Refreshed daily, it is an analytically independent research and post-trade intelligence view within the NEM Dashboard, not a live operational terminal, and every estimate retains a visible method and boundary.

The shorter editorial expression is: **ChargeTrace explains how finite stored energy is converted into grid flexibility and observable market value, and whether each battery captured the opportunity available to it.**

### Original MVP

The original three-asset MVP covered Capital Battery, Blyth BESS, and Victorian Big Battery from 1 to 30 July 2026. It proved independent registry loading, date-addressable AEMO ingestion, five-minute dispatch and price views, published stored energy, a daily-cycle calendar, observable energy and ten-service FCAS value, quality states, and asset comparison. The same-day expanded iteration superseded it with 17 physical assets, a longer validation window, fleet context, an opportunity-capture benchmark, and the strategy guide. The original scope remains recorded here so the change in ambition is visible.

### Current state and identity

**ChargeTrace** is an evolving Energy Systems view inside the NEM Dashboard at `/nem/charge-trace/`. Its detailed educational guide is at `/nem/charge-trace/guide/`. The former `/charge-trace/`, `/battery-explorer/`, and `/nem/battery-explorer/` addresses are permanent compatibility redirects. It shares the suite's navigation and scheduler, while keeping a separate Django app, registry, database tables, calculations and failure boundary.

The public name is **ChargeTrace**. "NEM Battery Dispatch and Value Stack Explorer" is the analytical description. The interface may use "Australia's grid battery explorer" as a short identity line, but scope copy must make clear that the operational dataset covers selected grid-scale batteries in the National Electricity Market. It does not cover Western Australia's WEM, every consumer battery, or every NEM battery.

**Maturity:** expanded MVP, locally implemented and populated on 10 August 2026.  
**Primary audience:** senior energy trading strategists, battery asset and portfolio analysts, energy-market practitioners, investors, policy and system-planning audiences, and informed readers learning battery fundamentals.  
**Cadence:** daily refresh at 09:00 Australia/Sydney, normally complete through the latest common source date two days behind wall-clock time.  
**Product type:** forensic market intelligence and post-trade research, not a live dispatch terminal or trading recommendation system.

### Battery fundamentals and system role

A battery is an energy-limited, reversible asset, not a primary energy source. It buys or absorbs electricity while charging, stores most of it chemically, and returns a smaller quantity later. Its core quantities are:

- **MW, power:** how quickly the asset can charge or discharge;
- **MWh, energy:** how much electrical energy the public nameplate says it can store; and
- **duration, MWh divided by MW:** approximate full-power endurance.

The physical facility combines cell racks, a battery-management system, bidirectional inverters or power-conversion systems, transformers, cooling, protection, communications, and an energy-management or optimisation layer. In the NEM, the battery bids as both load and generation through a bidirectional registration. AEMO dispatches it every five minutes while co-optimising regional energy and frequency-control ancillary services.

Grid batteries can provide intraday energy shifting, negative-price absorption, evening-peak capacity, fast frequency response, renewable ramp management, curtailment reduction, network support, system-integrity reserve, voltage support, and grid-forming capability. They remain constrained by duration, efficiency, degradation, location, network limits, and finite state of charge. They complement rather than eliminate transmission, demand response, hydro, and other firm capacity.

The modern energy-economy role is both physical and commercial. Batteries translate variable low-marginal-cost renewable supply into controllable flexibility. At fleet scale they also reshape price formation: daytime charging raises the lowest prices, evening discharge suppresses the highest prices, and FCAS competition reduces ancillary-service prices. The system benefits while the merchant spread can narrow. This cannibalisation effect is central to the product thesis.

### What a senior trading strategist wants

The strategist is not satisfied by "the battery discharged at a high price." They want to determine whether that was the best use of a scarce stored MWh given information, constraints, and alternative services. The product direction is organised around five layers:

1. **Physical position:** state of charge, availability, maximum charge and discharge, active DUIDs, storage headroom, unit outages, and time near limits.
2. **Market state:** regional RRP, all FCAS prices, net demand, wind and solar conditions, interconnectors, constraints, outages, and aggregate battery behaviour.
3. **Decision quality:** immediate value versus the opportunity cost of preserving energy, actual versus target, feasible hindsight value, capture ratio, and missed high-value windows.
4. **Commercial decomposition:** charging cost, discharge value, energy margin, gross FCAS enablement value, negative-price charging benefit, event concentration, and normalised value per MW, MWh, cycle, and discharged MWh.
5. **Forward structure:** new fleet capacity, duration mix, competitor behaviour, spread compression, FCAS cannibalisation, and the shift toward contracted capacity, network, portfolio, and grid-forming value.

Public data cannot reveal the participant's full information set, contracts, degradation curve, internal risk limits, or network obligations. The product therefore supports disciplined diagnosis rather than retrospective accusation.

### Current Australian market context

The July 2026 AEMO Generation Information register contains 5,947.18 MW and 12,383.66 MWh of battery capacity under the strict `In Service` classification. AEMO's broader Quarterly Energy Dynamics measure reports more than 9 GW installed by the end of Q2 2026 because it includes batteries progressing through commissioning. Those measures are both valid within their definitions and must not be added or compared without the status explanation.

The Q2 2026 market result demonstrates the thesis: average NEM battery discharge reached 476 MW, battery charging and discharging materially influenced price setting, but the fleet's captured price spread fell to $51/MWh and estimated energy-plus-FCAS revenue fell to $57.5 million. More activity did not produce proportionally more market revenue.

Primary contextual sources:

- [AEMO Generation Information](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/nem-forecasting-and-planning/forecasting-and-planning-data/generation-information)
- [AEMO Quarterly Energy Dynamics](https://www.aemo.com.au/energy-systems/major-publications/quarterly-energy-dynamics-qed)
- [AEMO 2026 Integrated System Plan](https://www.aemo.com.au/-/media/files/major-publications/isp/2026/2026-integrated-system-plan-isp.pdf)

### Implemented fleet coverage

The effective-dated registry contains 17 physical ChargeTrace assets and 18 DUID registrations across New South Wales, Queensland, South Australia, and Victoria. Western Downs has two independently dispatched DUIDs aggregated into one physical site. The three Melbourne Renewable Energy Hub connections remain separate assets because AEMO publishes them as separate sites and registrations.

| Asset | Region | DUID | MW | MWh | Approx. duration |
|---|---:|---|---:|---:|---:|
| Capital Battery | NSW1 | `CAPBES1` | 99.99 | 199.98 | 2.0 h |
| Eraring Big Battery | NSW1 | `ERB01` | 460.00 | 1,773.00 | 3.9 h |
| Tarong BESS | QLD1 | `TARBESS1` | 300.00 | 600.00 | 2.0 h |
| Swanbank BESS | QLD1 | `SWANBBF1` | 266.34 | 531.30 | 2.0 h |
| Supernode BESS | QLD1 | `SNB01` | 259.92 | 619.40 | 2.4 h |
| Western Downs Battery | QLD1 | `WDBESS1`, `WDBESS2` | 509.60 | 1,019.20 | 2.0 h |
| Brendale BESS | QLD1 | `BRNDBES1` | 204.96 | 409.92 | 2.0 h |
| Greenbank BESS | QLD1 | `GREENB1` | 200.00 | 400.00 | 2.0 h |
| Blyth BESS | SA1 | `BLYTHB1` | 200.32 | 400.00 | 2.0 h |
| Torrens Island BESS | SA1 | `TIB1` | 250.70 | 249.61 | 1.0 h |
| Victorian Big Battery | VIC1 | `VBB1` | 300.00 | 470.00 | 1.6 h |
| Rangebank BESS | VIC1 | `RANGEB1` | 224.00 | 400.00 | 1.8 h |
| MREH A1 | VIC1 | `MREHA1` | 216.16 | 399.84 | 1.9 h |
| MREH A2 | VIC1 | `MREHA2` | 216.16 | 399.84 | 1.9 h |
| MREH A3 | VIC1 | `MREHA3` | 215.60 | 800.80 | 3.7 h |
| Hazelwood BESS | VIC1 | `HBESS1` | 200.07 | 162.00 | 0.8 h |
| Koorangie Energy Storage System | VIC1 | `KESSB1` | 193.00 | 385.00 | 2.0 h |
| **ChargeTrace total** |  | **18 DUIDs** | **4,316.82** | **9,219.89** |  |

Against the July register's strict in-service denominator, this is **72.6% of NEM battery MW and 74.5% of MWh**. It is a material operating cohort rather than complete fleet coverage. Queensland, the largest strictly in-service region by MW, is represented. Tasmania has no strict in-service grid-battery row in the July snapshot. The WEM is outside scope.

The 1 July to 8 August 2026 validation and publication window contains:

- 39 operating days;
- 202,176 battery unit intervals;
- 663 daily asset summaries;
- 646 complete summaries; and
- 17 partial summaries caused by missing individual AEMO energy-storage readings.

Public capacity discrepancies, including storage above nameplate or below zero, remain visible as advisories but no longer make an otherwise complete day "partial." A day is partial when expected interval, SCADA, or storage coverage is missing. A multi-unit site's completeness expectation is 288 intervals multiplied by its number of active registrations.

### Source and calculation boundary

ChargeTrace uses three AEMO source families:

| Layer | Source | Published use | Boundary |
|---|---|---|---|
| Asset registry | Generation Information plus reviewed DUID mapping | Physical site, region, public MW and MWh, DUID, owner or custodian, effective dates | Hybrids, augmentations, cutovers, and duplicate register rows require review |
| Unit dispatch and storage | NEMWeb Next Day Dispatch `UNIT_SOLUTION` | Initial MW, target, availability, ten FCAS enablements, initial and projected energy storage | Storage is AEMO's dispatch series, not a battery-management-system reading |
| Actual power | Dispatch SCADA `UNIT_SCADA` | Five-minute signed operational power | SCADA is operational, not final settlement metering |
| Prices | DispatchIS `PRICE` | Regional RRP and ten FCAS prices | Regional price is not a nodal opportunity and omits contracts and settlement adjustments |

MVP arithmetic is transparent:

1. Signed five-minute energy equals SCADA MW divided by 12. Positive is discharge and negative is charging.
2. Energy-market value equals signed MWh multiplied by regional RRP. Negative-price charging can create positive observable value.
3. Gross FCAS value equals enabled MW multiplied by service price and divided by 12, summed across Raise and Lower 1 second, 6 second, 60 second, 5 minute, and Regulation services.
4. Observable gross value equals energy-market value plus gross FCAS enablement value.
5. Equivalent cycles equal discharged MWh divided by public storage capacity.
6. Storage values outside the public-capacity range are flagged rather than clipped.

The result is **estimated observable gross market value**, never participant profit, settled revenue, or a trading recommendation. It excludes effective transmission loss factors in the current release, market fees, settlement metering differences, hedges, tolling agreements, capacity contracts, degradation cost, auxiliary load, network-support obligations, private outages, private bids, and Frequency Performance Payment dollars.

### Opportunity-capture benchmark

The implemented opportunity view asks: given the public price path and a simplified physical envelope, how much energy-market value could a feasible hindsight schedule have captured?

The server-side benchmark uses a 201-level state-of-charge dynamic programme. It:

- uses the selected day's regional five-minute RRP;
- respects public MW and MWh capacity;
- begins and ends at the observed AEMO storage boundary;
- respects five-minute charge and discharge limits;
- assumes 90% round-trip efficiency, split symmetrically across charge and discharge;
- holds, charges, or discharges at each interval to maximise energy value; and
- excludes FCAS co-optimisation, degradation, bids, contracts, outages, loss factors, and risk.

The chart overlays actual dispatch, the benchmark schedule, spot price, and the lowest and highest 15% price windows. Summary cards show actual energy value, feasible hindsight value, capture ratio, and observed start-to-end storage.

The benchmark must never be called lost profit. A ratio below 100% may reflect FCAS reservation, degradation management, a contract, a network obligation, an outage, risk, or information unavailable to the model. A ratio above 100% can occur because observed dispatch is continuous while the public benchmark discretises storage. The product calls it a **public-data capture ratio** and keeps the caveat expandable beside the chart.

### Implemented visual and narrative hierarchy

The current page contains:

1. ChargeTrace identity, a plain-language purpose statement, and NEM Dashboard membership badges. Redundant guide and project-catalogue links are deliberately absent from the hero.
2. A collapsible project thesis near the top.
3. A daily refresh strip showing the 09:00 schedule, current data-through date, and "Not live data."
4. One page-level **Week / 3 Months** switch. It changes the reporting basis for every headline KPI and period comparison together.
5. Asset and period-ending controls with MW, MWh, and duration chips.
6. A selected-range overview that states published days, expected days, and any incomplete-history coverage explicitly.
7. Four period KPI cards for observable gross value, energy-market value, gross FCAS value, and public-data opportunity capture.
8. A dark **Build the foundations** guide callout immediately after the KPI summary and before the analytical charts.
9. A period-operation chart: daily observations for Week and weekly aggregation for 3 Months. Its local control switches between physical charge/discharge plus observable value, and energy/FCAS value plus cycling intensity.
10. A period opportunity chart comparing actual energy value with the stored feasible hindsight benchmark. Its local control switches between dollar value and a capture-rate lollipop view against the 100% hindsight reference.
11. A period cycle heatmap and period value-stack split.
12. A period-matched cohort comparison using absolute value, value per discharged MWh, and cycles.
13. A collapsed five-minute day inspector containing signed dispatch and regional spot price, AEMO-published stored energy, daily opportunity detail, quality notes, and ten-service FCAS detail.
14. Fleet coverage using a compact east-coast state-tile grid, plus a power-versus-duration landscape for the largest in-service sites.
15. A growth-versus-cannibalisation chart.
16. The calculation method, source provenance, refresh time, and exclusions.

The range semantics match the publication cadence. **Week** is the default and means the latest seven published days. **3 Months** is a rolling 91-calendar-day window ending at the selected monthly anchor and is plotted as weekly buckets. The interface never manufactures missing history: on 11 August 2026, the three-month view contains the 40 available days from 1 July to 9 August and displays both `40 of 91 days` and an available-history warning. Totals are neither scaled to a complete period nor extrapolated. Annual was deliberately removed because the dataset is not yet deep enough to make that control useful.

The growth-versus-cannibalisation series uses AEMO Quarterly Energy Dynamics:

| Quarter | Average NEM battery discharge | Captured spread | Estimated energy plus FCAS revenue |
|---|---:|---:|---:|
| Q3 2025 | 215 MW | $123/MWh | $111.9m |
| Q4 2025 | 268 MW | $104/MWh | $70.4m |
| Q1 2026 | 359 MW | $121/MWh | $96.9m |
| Q2 2026 | 476 MW | $51/MWh | $57.5m |

This is not a simple monotonic proof of cannibalisation because weather, demand, outages, and FCAS events also change quarterly revenue. It is a market-structure signal: activity and capacity have grown much faster than the captured spread or total observable market pool.

### Design relationship to the original concept image

The [original NEM battery dispatch and value-stack concept](images/nem-battery-dispatch-value-stack-concept.png) remains the visual reference. The implementation preserves its warm editorial palette, serif display type, compact controls, dispatch-first narrative, rounded analytical cards, orange charging, green discharging, navy price line, and dense but ordered desktop composition.

Intentional differences improve truthfulness or product hierarchy:

| Concept or ideal | Implemented decision | Reason |
|---|---|---|
| Broad Australian battery-explorer implication | NEM scope and actual percentage coverage are visible | Avoids implying WEM or complete national coverage |
| Decorative storage confidence ribbon | AEMO-published storage plus public-capacity reference and gap states | No invented uncertainty band |
| Daily-first interface despite a weekly publication promise | One global Week / 3 Months control, with five-minute detail in a collapsed inspector | The primary analytical grain now matches the stated update cycle while retaining forensic depth |
| One fixed visual encoding per question | Local Energy flow / Value mix and Dollar value / Capture rate controls | Lets a strategist move between physical, financial, absolute, and normalised interpretations without changing the selected range |
| Ambiguous intraday cycles grid | Range-aware daily or weekly cycle heatmap | Equivalent cycles are aggregated at the selected reporting grain |
| Value donut as the full commercial answer | Donut retained as a compact split, with explicit charging cost and detailed FCAS drill-down | Preserves scanability while naming exclusions |
| Comparison dominated by total dollars | Dollars remain, but value per discharged MWh and cycles add normalisation | Scale and operating intensity are different questions |
| No answer to "was it good?" | Opportunity-capture chart and constrained benchmark | Moves from description toward decision-quality research |
| No market or fleet context | Regional coverage, duration landscape, and quarterly cannibalisation view | Places one asset inside the changing market structure |
| Sparse floating regional cards | A filled NEM tile map arranged QLD → NSW → VIC/TAS with SA to the west | Makes regional relationships legible without claiming geographic precision |
| Long thesis in the first viewport | Collapsible 200-word thesis | Purpose is available without dominating the tool |
| Full education inside the dashboard | Separate guide route | Keeps the explorer analytical while supporting readers with weaker battery knowledge |

The page is intentionally long because it progresses from release status to asset evidence, opportunity assessment, fleet context, and method. Each major analytical layer has a distinct heading and explanatory boundary. Further cards should not be added unless they answer a new decision question.

### Educational strategy guide

`/nem/charge-trace/guide/` contains a 2,091-word first-principles essay titled **How a grid battery really works**. It is part of the product, not a detached blog post. It begins with the basic idea that a battery moves electricity through time, then adds complexity through:

1. MW, MWh, and duration;
2. cells, battery management, inverters, transformers, and the optimiser;
3. round-trip losses and degradation;
4. five-minute NEM bidding, dispatch, prices, and the bidirectional-unit model;
5. energy arbitrage and all FCAS timescales;
6. renewable integration, system security, price shaping, and grid forming;
7. opportunity cost under uncertainty;
8. the physical, market, decision-quality, commercial, and forward questions a senior strategist asks; and
9. how to interpret every major ChargeTrace visual without confusing a benchmark with profit.

The guide uses the same visual system as the explorer but a narrower reading width, upright body copy, larger line spacing, definition cards, and analytical asides. It links back to the explorer and cites AEMO Generation Information, Quarterly Energy Dynamics, and the 2026 Integrated System Plan.

### Independent architecture and maintainability

`nem_battery_explorer` owns its models, migrations, registry, source readers, calculations, benchmark, management commands, tests, templates, CSS, JavaScript, and refresh audit. It does not import from `nem_dashboard`, `nem_price_lab`, or `gas_monitor`. Sharing Django, PostgreSQL, navigation, and deployment infrastructure is platform reuse rather than analytical coupling.

The maintenance design is intentionally small:

1. `data/battery_registry_v1.json` is the reviewed, effective-dated source of physical assets and registrations.
2. `load_battery_registry` validates and idempotently applies registry changes.
3. `refresh_battery_data` downloads each required AEMO archive once, filters every selected DUID from the same files, validates coverage, and upserts intervals and summaries.
4. Source receipts record URL, filename, byte count, and SHA-256 checksum.
5. Page requests use local PostgreSQL only. They never call AEMO.
6. A failed run leaves the last complete public dataset online.
7. Daily summaries persist the versioned opportunity benchmark value and capture ratio, so Week and 3 Months pages aggregate a stable derived layer instead of recomputing hundreds of optimisation runs on each request.
8. `recalculate_battery_summaries` rebuilds the derived daily layer and benchmark without downloading source files when calculation logic changes.
9. The source cache makes retries and historical rebuilding cheaper.

The 17-asset expansion does not multiply source downloads. AEMO's files already contain the wider NEM dispatch set; the added cost is local filtering, validation, and database rows. The one-off 39-day rebuild took materially longer than a normal incremental update. Each daily job processes only newly available dates after the last stored summary.

Production scheduling remains server configuration, not web-request behavior. The unified service runs at 09:00 Australia/Sydney every day and ChargeTrace keeps its Week and 3 Months analytical ranges while gaining fresher underlying observations. Exact commands, timer configuration, verification, and repair steps live only in `docs/DEPLOYMENT.md`.

### Verification, 11 August 2026

- Registry load: 17 assets and 18 registrations.
- Historical rebuild plus current refresh: 207,360 interval rows and 680 daily summaries through 9 August 2026.
- Data quality: 663 complete summaries and 17 partial summaries with visible storage-coverage notes.
- Coverage: 4,316.82 MW and 9,219.89 MWh, equal to 72.6% and 74.5% of the strict July in-service register totals.
- Opportunity example: the default Victorian Big Battery day produces a physically bounded schedule below its 300 MW public power limit and a clearly caveated public-data capture ratio.
- Period controls: Week renders seven daily points; 3 Months renders the available 40 of 91 days in six weekly buckets. Incomplete history is visibly counted and is not extrapolated.
- Alternate chart views: physical flow/value mix and dollar opportunity/capture rate are keyboard-accessible buttons with synchronized legends.
- Benchmark coverage: all 680 daily summaries hold the persisted opportunity benchmark fields.
- Rendering: the database-backed explorer and guide return HTTP 200; the explorer response includes all 17 asset options plus 40 calendar dates.
- JavaScript syntax: clean under `node --check`.
- Current verification: all 270 repository tests pass; `manage.py check`, migration drift checks, Python compilation and `git diff --check` are clean. The live local refresh brought price data through 11 August, gas through 10 August, and fuel and battery data through 9 August 2026.

### Roadmap summary

The scheduled task is production activation and observation of the unified daily release. Planned work expands clean history and reconciliation, adds loss-adjusted estimates, deepens operational and event analysis, improves practical and sensitivity benchmarks, and adds auditable exports and accessible interactions. See Part 3.

### Known boundaries

- NEM only; no WEM and no consumer-battery operation.
- 72.6% of strict in-service MW, not complete fleet coverage and not the broader commissioned-plus-commissioning measure.
- Current history begins 1 July 2026 in the populated development dataset; the clean method can extend to 1 July 2025 before legacy paired-DUID research is attempted.
- Public storage is an AEMO dispatch field, not a BMS measurement.
- Regional RRP is not a nodal price and does not reveal network or contract obligations.
- The value stack is gross and observable, not settled or private participant economics.
- The opportunity model is energy-only perfect hindsight with simplified efficiency and capacity. It does not reproduce the participant's optimiser.
- Quarterly growth and revenue comparisons are affected by weather, demand, outages, scarcity events, and regional FCAS conditions as well as competition.
- Fleet totals are a dated July 2026 snapshot and require periodic registry review.

### Product evolution

| Site release | Date | Change | Product consequence |
|---|---|---|---|
| `Candidate 2.8.0`  10 Aug 2026 | Three-asset, 30-day data spike completed | Proved post-IESS dispatch, storage, energy, and ten-service FCAS feasibility |
| `Candidate 2.8.0`  10 Aug 2026 | Independent Django app and `/charge-trace/` route completed | Separated the project from both existing NEM applications |
| `Candidate 2.8.0`  10 Aug 2026 | Monday 08:00 weekly release contract adopted | Made the public cadence and maintenance obligation explicit |
| `Candidate 2.8.0`  10 Aug 2026 | Initial interface matched the concept with conservative financial language | Shipped dispatch, storage, cycles, value stack, comparison, quality, and method views |
| `Candidate 2.8.0`  10 Aug 2026 | Registry expanded to 17 assets and 18 DUIDs | Increased strict in-service coverage to 72.6% of MW and added Queensland |
| `Candidate 2.8.0`  10 Aug 2026 | Opportunity-capture benchmark added | Introduced decision-quality research without labelling the gap lost profit |
| `Candidate 2.8.0`  10 Aug 2026 | Fleet coverage and growth-versus-cannibalisation views added | Connected individual asset behavior to market structure |
| `Candidate 2.8.0`  10 Aug 2026 | Collapsible thesis and 2,091-word strategy guide added | Made the product legible to both senior specialists and readers learning from first principles |
| `Candidate 2.8.0`  11 Aug 2026 | Moved under `/nem/charge-trace/` and joined the daily NEM-suite refresh | Preserved analytical and schema independence while giving users one market product and one operating schedule |

---

# Part 3: Roadmap

The roadmap records future work that has been discussed and accepted as belonging to the site. It does not require every item to have a date. It separates an accepted direction from a scoped plan and from work tied to a delivery window.

## 3.1 Roadmap contract

| Phase | Meaning | Required information |
|---|---|---|
| Idea phase | The direction belongs to the product, but the solution or scope is still open | Intended outcome, why it belongs, and the question still to resolve |
| Planned | The outcome and acceptance boundary are understood, but no delivery window is committed | Scope, dependencies, and acceptance criteria |
| Scheduled | The work is tied to a date, release, or operating event | Target window, dependencies, and acceptance criteria |

A roadmap idea differs from a parking-lot item. A roadmap idea is expected to be built when its shape becomes clear. A parked idea remains deliberately uncommitted because value, priority, feasibility, maintenance, or evidence is insufficient.

Each roadmap item has one stable ID. Part 2 project records reference those IDs rather than restating the plan. When work ships, it leaves Part 3 and is recorded in the affected project evolution table and the Part 1 release ledger.

## 3.2 Scheduled

A target may be a release or operating event rather than a calendar date.

| ID | Project | Intended outcome | Target | Dependencies | Acceptance criteria |
|---|---|---|---|---|---|
| `SITE-S01` | Site-wide | Upgrade vulnerable or stale dependencies one at a time and review production security | Candidate release `2.8.0` | Full test suite and lockout-safe server procedure | Tests and `check --deploy` pass; authentication, forms, uploads, articles, audio, and analytical pages are smoke-tested |
| `SITE-S02` | Portfolio | Verify production contact delivery without exposing the recipient | Before the next production release | Valid mail-provider and recipient configuration | A real message is delivered, zero-send is treated as failure, and no private address appears client-side |
| `SITE-S03` | Site-wide | Prevent returning browsers from retaining stale static assets | Candidate release `2.8.0` | Storage choice and production `collectstatic` check | Content-hashed assets or an explicitly versioned interim strategy is active and verified |
| `NEMF-S01` | NEM Dashboard | Correct aggregated fuel units and misleading payload names | Next release affecting the fuel view | Regression tests for totals and labels | Seven-day energy is labelled MWh and MW is used only for instantaneous quantities |
| `NEM-S01` | NEM Dashboard suite | Deploy and observe the unified 09:00 daily refresh | First production release of the unified suite | Database backup, source access, ML requirements, systemd installation, logs, and source caches | One automatic run updates all four views, the Sunday origin is not rewritten, public currency matches stored data, and failures are visible in the journal |

## 3.3 Planned

| ID | Project | Intended outcome | Dependencies | Acceptance criteria |
|---|---|---|---|---|
| `SITE-P01` | Site-wide | Add continuous integration for Django checks and tests | CI environment without production secrets | Every push installs dependencies, runs `manage.py check`, runs tests, and checks JavaScript syntax where applicable |
| `SITE-P02` | Site-wide | Complete a cross-site accessibility review | Stable pages and representative data | Keyboard order, focus, contrast, reduced motion, dialogs, mobile layout, and chart alternatives are reviewed and defects recorded or fixed |
| `PP-P01` | Portfolio Pulse | Create versioned monthly account snapshots and labelled outcome history | Privacy, retention, deletion, and outcome definitions | Historical replay separates what was known at each date and supports temporal evaluation of transparent models |
| `LC-P01` | Life Compass | Automate the external frontend build and safe asset handoff | Access to `personal_dashboard` and validated target paths | One command builds, copies hashed assets, removes only validated stale files, and leaves templates referencing existing assets |
| `NEMP-P01` | Price Predictor Lab | Add a leakage-safe one-day-ahead model beside the seven-day product | Stable weekly evidence record and archived issue-time inputs | Horizon-appropriate inputs use correct vintages and the model is retained only if it beats transparent baselines |
| `GAS-P01` | Gas Monitor | Add hub prices with tested gas-day alignment | STTM, Gas Supply Hub, and DWGM time-boundary rules | Price and physical series share a documented comparable period and no untested conversion is plotted |
| `GAS-P02` | Gas Monitor | Add the system schematic, stress decomposition, and a defensible event replay | Prices plus completed source and route definitions | Components are traceable; inferred routes are labelled; the event uses valid demand coverage or states its narrower boundary |
| `WORLD-P01` | World Ledger | Add coverage-confidence and rank-robustness evidence | Source-vintage metadata and scenario method | Every rank can show source recency and a defensible range under plausible weight changes |
| `CT-P01` | ChargeTrace | Extend clean history, add monthly reconciliation, and alert on failed daily releases | Storage and retention plan | History reaches at least July 2025, revisions are reported, and a missed scheduled release is visible |
| `CT-P02` | ChargeTrace | Add effective transmission-loss factors and loss-adjusted estimates | Effective-dated loss-factor source | Gross regional-price and loss-adjusted estimates are separately labelled and reproducible |
| `CT-P03` | ChargeTrace | Add operational and event context | Target, availability, constraints, and event definitions | Target versus SCADA, availability, limits, headroom, and selected events are visible without implying private intent |
| `CT-P04` | ChargeTrace | Add a practical rules benchmark and sensitivity analysis | Stable current hindsight benchmark | Practical and upper-bound comparators are distinct and every efficiency, capacity, and degradation assumption is visible |
| `CT-P05` | ChargeTrace | Improve auditability and accessible interaction | Stable payload and export contract | CSV or table access, shareable event URLs, keyboard tooltips, and mobile chart interaction are delivered and tested |

## 3.4 Idea phase

| ID | Project | Intended direction | Question still to resolve |
|---|---|---|---|
| `NEM-I01` | NEM products | Fold fuel mix and price forecasting into one coherent NEM dashboard | When are both cadences stable enough that a merge reduces complexity instead of coupling moving products? |
| `WORLD-I01` | World Ledger | Expand the warehouse with observed demographics, industrial depth, electricity, finance, ownership, logistics, and infrastructure | Which sources meet the complete-cohort, observed-data, revision, and interpretation rules? |
| `WORLD-I02` | World Ledger | Add power-surplus, potential-gap, conversion-gap, trade-leverage, concentration, fragility, frontier, neighbour, velocity, and shock stories | Which stories add a distinct insight without overstating unlike score scales? |
| `PP-I01` | Portfolio Pulse | Evaluate trained retention and intervention models | Can sufficient longitudinal outcomes be obtained without creating privacy, leakage, or calibration problems? |
| `LC-I01` | Life Compass | Revisit the full-page background treatment | Can a higher-resolution source or different technique improve the page without blur, letterboxing, or reduced legibility? |
| `CT-I01` | ChargeTrace | Research pre-bidirectional-unit history, FCAS co-optimisation, emissions context, and deeper fleet profiles | Which extension is supportable from public data without turning observable value into a false profit claim? |

## 3.5 Roadmap review record

| Review date | Decisions | Next review |
|---|---|---|
| 10 Aug 2026 | Replaced the mixed backlog with Idea, Planned, and Scheduled phases; moved recurring commands to deployment; retained stable project IDs | 7 Sep 2026 |

# Part 4: Ideas parking lot

The parking lot contains worthwhile concepts that are not authorised roadmap directions. An item may remain parked for a long time, but it must state why it is parked and what evidence would justify reconsideration.

## 4.1 Active parking lot

| ID | Idea | Area | Why it may belong | Why parked | Promotion trigger | Last reviewed |
|---|---|---|---|---|---|---|
| `PARK-001` | Football or running analytics product | Human Performance | Adds an interactive product to a pillar represented mainly by articles and StillPoint | No durable user question or decision interaction has been selected | A defensible dataset and a question that is more than a chart gallery | 10 Aug 2026 |
| `PARK-002` | Portfolio Pulse PDF export | Portfolio Pulse | Could support controlled executive reporting | Browser print may already meet the need | Evidence that users need a fixed report artifact | 10 Aug 2026 |
| `PARK-003` | Separate gas line in the NEM trend | NEM Dashboard | May clarify fossil composition | Could weaken the central renewable-versus-fossil comparison | A tested visual adds insight without clutter | 10 Aug 2026 |
| `PARK-004` | Self-host main-site CDN dependencies | Site-wide | Reduces third-party requests and supply-chain exposure | Bundle ownership and benefit are not established | Bundle strategy agreed for Bootstrap, Chart.js, and fonts | 10 Aug 2026 |
| `PARK-005` | Main-site frontend build tooling | Site-wide | Could improve source maps and asset versioning | Current split CSS and compressor remain adequate | A measured pain point beyond scheduled cache busting | 10 Aug 2026 |
| `PARK-006` | Branded email alias | Portfolio | Adds professional polish | Depends on domain routing and provider verification | Forwarding configured and alias verified | 10 Aug 2026 |
| `PARK-007` | Portfolio Pulse CRM integration | Portfolio Pulse | Could turn a demonstration into an operating product | Privacy, authentication, ownership, and the CRM use case are undefined | One specific integration with an approved data and retention model | 10 Aug 2026 |
| `PARK-008` | Saved Portfolio Pulse customer history | Portfolio Pulse | Enables longitudinal analysis | Conflicts with the current stateless privacy boundary | Explicit demand plus secure storage, retention, export, and deletion design | 10 Aug 2026 |

## 4.2 Monthly review and promotion rules

The roadmap and parking lot are reviewed on the first Monday of each month. The review should:

1. move shipped roadmap work into the release ledger and project evolution tables;
2. confirm that Scheduled items still have a real delivery event;
3. refine Planned items when dependencies or acceptance criteria change;
4. decide whether each roadmap Idea still belongs;
5. review every parked item and choose Keep parked, Promote, Merge, Reject, or Retire; and
6. update the document-control dates and commit the review.

A parked item moves into the roadmap only when:

1. the target user and intended outcome are named;
2. required data exist or have an approved acquisition plan;
3. the smallest credible implementation can be stated;
4. it adds evidence not already supplied by another project;
5. privacy, operating ownership, and maintenance are understood; and
6. success and failure can both be evaluated honestly.

## 4.3 Disposition history

| Date | Item | Decision | Destination or reason |
|---|---|---|---|
| 6 Aug 2026 | NEM Spot Price Forecast Lab | Promoted and delivered | Became the Price Predictor Lab in Part 2.3; later work is tracked by `NEMP-*` roadmap IDs |
| 10 Aug 2026 | Automated NEM and energy-data ingestion | Split and promoted | Concrete Price Lab, Gas Monitor, and ChargeTrace activation work moved to `NEMP-S01`, `GAS-S01`, and `CT-S01`; operating commands moved to `docs/DEPLOYMENT.md` |
| 10 Aug 2026 | Life Compass background redesign | Moved to roadmap idea | Tracked as `LC-I01` because the direction belongs but the visual technique remains unresolved |
