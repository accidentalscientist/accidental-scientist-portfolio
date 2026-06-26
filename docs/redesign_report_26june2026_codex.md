# Accidental Scientist current site design and engineering review

Date reviewed: 26 June 2026  
Scope: local Django website code in `accidentalscientist2025`

## Executive summary

Accidental Scientist is currently a small, coherent Django portfolio site with three main product areas:

- a portfolio/blog layer for personal positioning, project launches, and long-form analytical writing;
- a NEM dashboard that turns uploaded fuel-mix CSV data into an interactive regional dashboard;
- Stillpoint, a minimalist meditation timer with optional guided-audio sessions.

The strongest architectural decision is that the site is becoming a publishing surface rather than the place where every analysis is authored. The separate Elite Analytics article workflow keeps large notebooks and analytical source material outside the website codebase, while the Django site imports clean article packages into editable `BlogPost` records.

The strongest design decision is the move toward a distinctive editorial identity: warm linen, forest green, terracotta, Playfair headings, Inter UI text, dark mode, and small marginalia elements. The site now has a recognisable point of view rather than feeling like a generic Bootstrap portfolio.

The largest engineering risks are not catastrophic, but they are real:

1. production security settings need tightening before relying on the deployment as final;
2. Markdown rendering currently assumes trusted content and should be sanitised if any untrusted content can enter the article pipeline;
3. CSV upload parsing for the NEM dashboard should be hardened against malformed files;
4. there are no automated tests yet;
5. some development/deployment configuration is still encoded directly in settings.

## Current architecture

### Django project structure

The project uses a conventional Django layout:

- `config/` contains global settings, URL routing, WSGI/ASGI entrypoints, and context processors.
- `portfolio/` contains the homepage, projects, blog, contact form, article import commands, and admin registration.
- `nem_dashboard/` contains the NEM fuel-mix models, admin upload flow, CSV parsing signal, dashboard view, template, and chart JavaScript.
- `stillpoint/` contains the meditation timer view, guided meditation model, template, and timer JavaScript.
- `static/` contains shared CSS, JavaScript, favicon/static identity assets, and NEM/Stillpoint front-end files.

### Data model decisions

The main content model is intentionally simple:

- `Project` stores project title, slug, description, optional image, optional project URL, and creation date.
- `BlogPost` stores title, slug, summary, key takeaway, Markdown content, cover image, publication date, status, category, featured flag, and optional external source URL.
- `BlogImage` stores ordered inline images for article placeholders such as `[[image1]]`.
- `Contact` stores submitted contact metadata, although the current contact flow emails rather than explicitly saving form submissions.
- `FuelDataUpload` stores uploaded CSV files for the NEM dashboard.
- `FuelGenerationData` stores parsed timestamp/state/fuel/supply records.
- `GuidedMeditation` stores Stillpoint guided audio files.

The important editorial choice is that `BlogPost` is not merely a notebook dump. It has `summary`, `key_takeaway`, `category`, `status`, `is_featured`, and inline images, which supports a more polished article presentation.

### Routing decisions

Current top-level route structure:

- `/` homepage
- `/projects/`
- `/projects/<slug>/`
- `/blog/`
- `/blog/<slug>/`
- `/contact/`
- `/nem/`
- `/stillpoint/`
- `/admin/`
- `/markdownx/`

This is clear and discoverable. The one mild naming issue is that the contact route is also used as the About page. That works, but longer term it may be cleaner to expose `/about/` and either redirect `/contact/` or keep contact as a section of about.

## Design decisions observed

### Visual identity

The CSS explicitly documents the design system as:

- Austrian: precise grid, mathematical spacing, restrained geometry;
- Indian: warm linen, terracotta accents, ornamental detail;
- French: Playfair editorial headings, journal-like typography, generous line-height.

Core design tokens:

- warm linen backgrounds;
- forest green primary text/accent;
- terracotta warm accent;
- muted sage secondary text;
- nearly-flat cards and fine borders;
- Playfair Display for editorial titles;
- Inter for UI and body text;
- Noto Sans Tamil for the footer Om glyph;
- dark-mode token overrides via `[data-theme='dark']`.

This is a strong and unusually personal identity. It is suitable for a website trying to signal data literacy, energy-transition seriousness, and a slightly literary/intellectual personality.

### Homepage

The homepage currently positions the site around:

- energy systems;
- data storytelling;
- human performance;
- the NEM dashboard as the primary call to action;
- current project;
- featured writing.

The typewriter effect rotates through topics such as Data Science, Energy Systems, Football Analytics, Grid Transition, Climate Policy, NEM Data, Human Performance, and Renewable Energy. This supports the multi-domain identity while still keeping energy transition prominent.

### Blog

The blog has moved toward an editorial publication pattern:

- category filters;
- a featured article card;
- list-style article rows;
- reading time;
- key takeaway;
- cover image;
- inline chart placement;
- source notebook links.

This is the right direction for the Elite Analytics workflow. The three-chart article style is especially strong: one hero image plus two inline figures keeps articles readable while still proving analytical depth.

### Projects

The project page is clean and energy-transition-oriented. Project rows are currently minimal and text-forward. This suits a portfolio, but as the project count grows, the page should eventually support:

- project type labels;
- status such as live/prototype/research;
- technology tags;
- a stronger launch card for the NEM dashboard;
- separate project-detail pages for non-embedded projects.

### NEM dashboard

The NEM dashboard presents:

- a 7-day summed fuel mix;
- region selector with auto-cycle;
- headline stats for total, renewables, coal, gas;
- grouped fuel bar;
- detailed fuel-type bars;
- 3-month renewables-vs-fossil line chart.

The dashboard is intentionally descriptive rather than theoretical. This is good. It avoids overclaiming and focuses on point-in-time/period fuel mix storytelling.

Current implementation note: JavaScript uses a 6-second auto-cycle, while the earlier roadmap mentioned 15 seconds. If 15 seconds remains the desired product behaviour, update `CYCLE_MS` in `nem_dashboard/static/nem_dashboard/js/fuel_chart.js`.

### Stillpoint

Stillpoint is implemented as a clean client-side meditation timer:

- Master mode: silent countdown with duration presets;
- Student mode: guided audio when audio exists in admin;
- SVG ring progress;
- local synthesized bell;
- simple mode switching.

It is a good early implementation. The aesthetic direction matches the stated “stoic safe space” goal, though this could eventually benefit from a more separate visual language from the main analytics site.

### Decorative assets

Current static identity assets include:

- transparent `favicon.png` and `favicon.ico`;
- `coastal_castle.svg`;
- `fleur-de-lys.png`.

The decorative marginalia — edge brick ribbon, footer fleur-de-lys, footer kolam/Om, and random page mark — gives the site character. These details should stay subtle. They work best as “signature texture,” not as primary content.

## Engineering decisions observed

### Environment-based configuration

Important runtime configuration is read from environment variables:

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- database credentials
- email credentials
- contact email
- optional `ELITE_ARTICLES_DIR`

This is the right general direction. `.env` is ignored by Git, which is important.

Current caveat: `STATIC_ROOT` is hard-coded to `/var/www/accidental-site/staticfiles`, which is production-specific. This is workable for the current DigitalOcean deployment, but better long-term practice would be to make it environment-configurable.

### Elite article import pipeline

The `import_elite_articles` command imports structured article packages from a separate source repository. It expects:

- `metadata.json`
- `article.md`
- cover image path;
- inline figure paths;
- source notebook links.

It updates or creates `BlogPost` by slug, saves cover images, and creates ordered `BlogImage` records.

This is a strong workflow decision because it separates:

- analytical source and notebooks;
- editorial article package;
- website presentation and publishing.

Recommendation: keep the Elite article source repository separate from the website code repository. The website should consume curated outputs, not become the main storage location for notebooks and raw analysis.

### Markdown rendering

Article content is rendered with `markdown2` and then inserted with `|safe` in the template. Inline images are injected by replacing `[[image1]]` placeholders before Markdown rendering.

This is acceptable if all Markdown is trusted and comes only from your own admin/editorial workflow. It is not safe for untrusted authors or arbitrary user-submitted Markdown unless sanitised.

### NEM dashboard data flow

CSV upload happens through the Django admin via `FuelDataUpload`. A `post_save` signal parses the CSV and bulk-inserts `FuelGenerationData`.

The dashboard view aggregates database records server-side and passes safe JSON to the front end via Django `json_script`, which is a good security practice.

### Front-end dependencies

The site currently loads external CDN assets:

- Bootstrap CSS/JS;
- Bootstrap Icons;
- Google Fonts;
- Chart.js.

This is convenient and fine for early development. For a hardened production posture, consider pinning with Subresource Integrity where possible, or self-hosting the assets.

## Security review

### Good security decisions already present

- Secrets are read from environment variables rather than hard-coded.
- `.env` is in `.gitignore`.
- CSRF middleware is enabled.
- Auth/session middleware is standard Django.
- Blog list/detail only exposes published posts whose publication date is not in the future.
- The NEM dashboard uses `json_script` for server-to-client data transfer.
- External links in templates generally use `rel="noopener"` when `target="_blank"` is present.
- The contact form uses Django form validation and CSRF protection.
- Admin-only flows are used for content, CSV upload, images, and guided audio.

### Security warnings from Django deploy check

`python manage.py check --deploy` reported five warnings in the current local environment:

1. `SECURE_HSTS_SECONDS` is not set.
2. `SECURE_SSL_REDIRECT` is not `True`.
3. `SESSION_COOKIE_SECURE` is not `True`.
4. `CSRF_COOKIE_SECURE` is not `True`.
5. `DEBUG` is currently `True` in the checked environment.

Recommended production settings once HTTPS is confirmed stable:

```python
DEBUG = False
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

Important: only enable long-lived HSTS after confirming HTTPS is fully working on the live domain and any subdomains you intend to serve.

### Markdown/XSS risk

Current risk: article Markdown is rendered to HTML and marked safe. Also, inline image captions are concatenated into HTML before Markdown rendering.

If all article content and captions are authored by you or imported from your controlled Elite article repo, this is a low operational risk. If anyone else can add articles, captions, notebooks, or metadata, this becomes a meaningful XSS risk.

Recommendation:

- either explicitly document that blog Markdown is trusted-admin-only content;
- or sanitise rendered HTML with `bleach` using a controlled allowlist of tags and attributes;
- escape inline figure captions before injecting them into HTML;
- consider moving figure rendering into templates rather than string-building HTML in the view.

### CSV upload risk

The NEM CSV parser assumes expected headers and valid numeric supply values. It can raise exceptions on malformed files, missing columns, non-numeric supply data, unusual encodings, or very large uploads.

Because upload is admin-only, this is not currently public-facing. It is still worth hardening because malformed data can break the admin save flow.

Recommendations:

- validate file extension and content type;
- enforce a maximum upload size;
- catch `KeyError`, `ValueError`, and `UnicodeDecodeError`;
- report import errors via Django messages/admin feedback instead of `print`;
- consider moving parsing out of a signal and into an explicit admin action or management command;
- add a uniqueness constraint/index for timestamp/state/fuel_type if re-import behaviour becomes important.

### Contact form risk

The contact form sends email directly and does not currently include spam protection or rate limiting. `django-recaptcha` is installed but not used.

Recommendations:

- add a honeypot field or reCAPTCHA;
- add per-IP rate limiting;
- fail gracefully if email settings are missing;
- consider saving `Contact` records as well as emailing, or remove the unused model if not needed.

### Admin and file upload risk

Admin controls images, article content, NEM CSVs, and guided meditation audio. That is fine for a personal site, but it makes admin account security important.

Recommendations:

- use a strong unique admin password;
- disable password login where possible or add MFA at the hosting/account layer;
- keep admin URL private-ish if desired, though security should not depend on obscurity;
- validate uploaded audio/image/file types;
- keep media serving restricted to static file serving only; never execute uploaded files.

### Dependency risk

The requirements file contains more packages than the visible code currently uses, including Wagtail-adjacent packages, Django REST framework, recaptcha, notebook tooling, and markdown tooling.

This is not a vulnerability by itself, but a larger dependency set increases update burden and possible attack surface.

Recommendations:

- periodically remove unused packages;
- run `pip-audit` or an equivalent dependency vulnerability scan before production deploys;
- pin versions intentionally and update on a schedule.

## Best-practices review

### Strengths

- The site has a clear model/view/template structure.
- Content has a draft/published lifecycle.
- Categories and key takeaways improve editorial control.
- The Elite import workflow is repeatable and mostly deterministic.
- The NEM dashboard uses server-side aggregation and safe JSON embedding.
- Static design tokens centralise colour and theme decisions.
- Dark mode is token-based rather than a duplicate stylesheet.
- No pending migrations were detected.

### Gaps

- There are currently no automated tests.
- `README.md` is out of date and has an incomplete code block.
- Production deployment steps are not documented in the repo.
- Some comments and symbols appear mojibaked in terminal output, suggesting encoding consistency should be checked.
- `import_notebooks.py` contains a hard-coded local Windows path and appears superseded by the Elite article workflow.
- `seed_data.py` deletes all projects and posts; it should be treated as development-only and ideally guarded.
- External CDN dependencies are not pinned with integrity hashes.
- `project_detail` can embed arbitrary admin-provided URLs in an iframe.
- NEM dashboard admin import flow should be more defensive.

## Prioritised recommendations

### Priority 1: before production confidence

1. Set production security settings for HTTPS, secure cookies, and `DEBUG=False`.
2. Confirm `.env` is not tracked and rotate any secrets that may have been exposed during development or terminal sharing.
3. Add Markdown sanitisation or document that Markdown is trusted-admin-only.
4. Harden NEM CSV parsing against malformed inputs.
5. Update deployment documentation for DigitalOcean/Gunicorn/Nginx/collectstatic/migrations.

### Priority 2: next engineering cleanup

1. Add a minimal test suite:
   - homepage returns 200;
   - blog list returns 200;
   - published article detail returns 200;
   - draft/future articles are hidden;
   - NEM dashboard handles no-data and sample-data states;
   - Stillpoint page returns 200.
2. Make `STATIC_ROOT` environment-configurable.
3. Remove or clearly mark legacy commands such as `import_notebooks.py` and destructive seed commands.
4. Add contact spam protection.
5. Add indexes/constraints to NEM data if dataset size grows.

### Priority 3: design/content polish

1. Add a dedicated `/about/` route and keep `/contact/` as an alias or section.
2. Improve project cards with tags, status, and stronger hero treatment for the NEM dashboard.
3. Split the large `style.css` into modules once it becomes painful to navigate.
4. Add a site-wide default OpenGraph image; the template currently references `images/share-default.png`, but that file was not present in the current static image listing.
5. Keep article pages to the successful pattern: concise narrative, one hero chart, two inline charts, and links to full notebook/source notebooks.

## Suggested target architecture

The best near-term architecture is:

```text
elite-analytics-articles-2026/
  articles/
    01_.../
      metadata.json
      article.md
      figures/
  notebooks/

accidentalscientist2025/
  portfolio/
    BlogPost + BlogImage
    import_elite_articles command
  nem_dashboard/
    admin CSV upload
    generated dashboard view
  stillpoint/
    timer + optional guided audio
```

The website should stay lightweight. The analytics repository should hold the research/notebook source. The website should import curated, polished article packages.

## Validation performed

Commands run locally:

- `python manage.py check`
- `python manage.py check --deploy`
- `python manage.py makemigrations --check --dry-run`
- `python manage.py test`

Results:

- normal Django check passed;
- no pending migrations detected;
- no tests currently exist;
- deploy check raised the five production security warnings listed above.

## Overall assessment

The site is in a good creative and architectural position. It has a real identity, a clear editorial direction, and a workable path for turning analytical notebooks into polished public writing.

The main work now is operational maturity:

- lock down production settings;
- sanitise or strictly trust Markdown;
- harden file imports;
- document deployment;
- add a small regression test suite.

Those changes would move the site from “promising personal portfolio under active construction” to “credible, maintainable publishing platform for energy-transition analytics.”
