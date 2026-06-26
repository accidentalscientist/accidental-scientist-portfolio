# Deployment runbook — accidentalscientist.net

The live site runs on a DigitalOcean droplet. The **served project** is
`/home/thibault/accidental-scientist-portfolio`, run by Gunicorn as user
`thibault` (systemd unit `gunicorn`). SSH in as `root`.

> Do **not** deploy to `/root/accidental-site` — that is a stale copy.

---

## Required environment variables (server `.env`)

In addition to the existing `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`,
database and email settings, the server **must** set:

```
STATIC_ROOT=/var/www/accidental-site/staticfiles
```

Optional production hardening (enable once HTTPS is confirmed stable):

```
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
```

(HSTS and SSL-redirect are intentionally off by default so a misconfigured
proxy can never lock the site out. The other security headers — secure
cookies, nosniff, X-Frame-Options — apply automatically whenever `DEBUG=False`.)

Nginx must forward the protocol header so Django knows it is behind HTTPS:

```
proxy_set_header X-Forwarded-Proto $scheme;
```

---

## Standard deploy (site code)

```bash
# 1. Pull
sudo -u thibault git -C /home/thibault/accidental-scientist-portfolio pull origin main

# 2. Dependencies
sudo -u thibault /home/thibault/accidental-scientist-portfolio/venv/bin/pip \
  install -r /home/thibault/accidental-scientist-portfolio/requirements.txt

# 3. Migrate
sudo -u thibault bash -c 'cd /home/thibault/accidental-scientist-portfolio && venv/bin/python manage.py migrate'

# 4. Collect static  (if it errors on permissions, run the chown below first)
sudo chown -R thibault:www-data /var/www/accidental-site/staticfiles
sudo -u thibault bash -c 'cd /home/thibault/accidental-scientist-portfolio && venv/bin/python manage.py collectstatic --noinput'

# 5. Restart
sudo systemctl restart gunicorn
```

## Deploy articles (separate repo)

```bash
sudo -u thibault git -C /home/thibault/elite-analytics-articles-2026 pull origin main
sudo -u thibault bash -c 'cd /home/thibault/accidental-scientist-portfolio && venv/bin/python manage.py import_elite_articles --publish'
```

The import is idempotent (`update_or_create` by slug). Cover images only
appear if the article packages are actually **pushed** to GitHub — confirm
`git log origin/main..HEAD` is empty in the articles repo before importing.

---

## Data that does NOT travel through git

`media/` is gitignored and some state lives only in the database, so after a
deploy that adds projects / audio / NEM data, set them up on the server:

- **Project rows** (Stillpoint project, NEM title/category) — via a
  `manage.py shell` heredoc (see release notes), or the admin.
- **Project categories** — NEM = Energy transition, Stillpoint = Human performance.
- **Guided meditation audio** — upload an **MP3** via admin → Stillpoint →
  Guided meditations (WAV is rejected).
- **NEM data** — upload a CSV via admin → Nem_dashboard → Fuel data uploads.
  Columns: `DateTime, State, Fuel Type, Supply`. The import summary appears on
  the upload row.

---

## Pre-deploy checks (run locally)

```bash
venv/Scripts/python manage.py check
venv/Scripts/python manage.py test
# On a production-like config:
venv/Scripts/python manage.py check --deploy
```

Do not deploy if `check` or the tests fail.

---

## Rollback

```bash
# find the previous good commit
sudo -u thibault git -C /home/thibault/accidental-scientist-portfolio log --oneline -5
# roll back
sudo -u thibault git -C /home/thibault/accidental-scientist-portfolio reset --hard <good_sha>
sudo -u thibault bash -c 'cd /home/thibault/accidental-scientist-portfolio && venv/bin/python manage.py migrate'
sudo systemctl restart gunicorn
```

Migrations are forward-only by default — if a release added a migration, roll
back to the matching code commit before the schema change, or reverse the
specific migration with `migrate <app> <previous_migration>`.

---

## Recurring gotchas

- **collectstatic permission denied** → `sudo chown -R thibault:www-data /var/www/accidental-site/staticfiles`, then re-run.
- **Two servers / wrong directory** → only `/home/thibault/accidental-scientist-portfolio` is live.
- **Git "dubious ownership"** → `git config --global --add safe.directory <path>` once.
