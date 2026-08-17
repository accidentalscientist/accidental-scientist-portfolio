# Deployment and data-operations runbook — accidentalscientist.net

This is the sole operational document for releasing, operating, refreshing, and recovering the Accidental Scientist site. Product purpose, design, history, roadmap, and parking decisions belong in `docs/DESIGN.md`.

# 1. Standard update or deployment

Use this section when a code, template, static, dependency, schema, or production-configuration change is ready to go live.

## 1.1 Choose and record the version

The public version uses `MAJOR.MINOR.PATCH`:

- **Major:** fundamental site repositioning, design-system replacement, or incompatible architecture change.
- **Minor:** a new project or substantial user-facing capability.
- **Patch:** a fix, copy or accessibility improvement, small visual refinement, or operational correction.

Every deployment containing a changed artifact receives a new version. Re-deploying the identical commit keeps its version. Article publication and routine data refreshes are operations, not site releases, and do not bump the site version.

Before committing the release:

1. Update `SITE_VERSION` in `config/context_processors.py`.
2. Update the affected Part 2 current-state and product-evolution sections in `docs/DESIGN.md`.
3. Remove delivered roadmap items from Part 3.
4. Add or complete the release-ledger row in Part 1.7.
5. Commit the intended release, tag it `vMAJOR.MINOR.PATCH`, and push both the commit and tag.

Do not mark production verified in the design document until the post-deployment checks below pass.

## 1.2 Local release checks

From the repository root on Windows:

```powershell
venv\Scripts\python.exe manage.py makemigrations --check --dry-run
venv\Scripts\python.exe manage.py check
venv\Scripts\python.exe manage.py test
venv\Scripts\python.exe manage.py check --deploy
git diff --check
git status --short
```

`check --deploy` must be run with production-like security settings. Review every intended file in `git status`; unrelated work must not be swept into the release.

Create and push the release only after the checks pass:

```powershell
git tag -a v2.8.0 -m "Release v2.8.0"
git push origin main
git push origin v2.8.0
```

Replace `2.8.0` with the chosen version. The user performs pushes and production SSH commands unless they explicitly delegate them.

## 1.3 Production deploy

The live project is `/home/thibault/accidental-scientist-portfolio`, run by Gunicorn as user `thibault` through the `gunicorn` systemd unit. `/root/accidental-site` is a stale copy and must not be used.

Before a release containing migrations or material data transformations, confirm that a current DigitalOcean/PostgreSQL backup or snapshot exists. Record its timestamp. Do not print database passwords into the terminal history.

Run as a server administrator:

```bash
# Fetch and fast-forward the release branch
sudo -u thibault git -C /home/thibault/accidental-scientist-portfolio fetch origin main --tags
sudo -u thibault git -C /home/thibault/accidental-scientist-portfolio checkout main
sudo -u thibault git -C /home/thibault/accidental-scientist-portfolio pull --ff-only origin main

# Confirm the exact release artifact
sudo -u thibault git -C /home/thibault/accidental-scientist-portfolio describe --tags --exact-match

# Install runtime dependencies
sudo -u thibault /home/thibault/accidental-scientist-portfolio/venv/bin/pip install -r /home/thibault/accidental-scientist-portfolio/requirements.txt
sudo -u thibault /home/thibault/accidental-scientist-portfolio/venv/bin/pip install -r /home/thibault/accidental-scientist-portfolio/requirements-ml.txt

# Check, migrate, and collect static assets
sudo -u thibault bash -c 'cd /home/thibault/accidental-scientist-portfolio && venv/bin/python manage.py check'
sudo -u thibault bash -c 'cd /home/thibault/accidental-scientist-portfolio && venv/bin/python manage.py migrate'
sudo chown -R thibault:www-data /var/www/accidental-site/staticfiles
sudo -u thibault bash -c 'cd /home/thibault/accidental-scientist-portfolio && venv/bin/python manage.py collectstatic --noinput'

# Restart and confirm the service
sudo systemctl restart gunicorn
sudo systemctl is-active gunicorn
sudo journalctl -u gunicorn --since '10 minutes ago' --no-pager
```

If `describe --tags --exact-match` fails, stop: the production commit is not the tagged release you intended to deploy.

## 1.4 Post-deployment verification

```bash
curl -fsS https://accidentalscientist.net/ > /dev/null
curl -fsS https://accidentalscientist.net/projects/ > /dev/null
curl -fsS https://accidentalscientist.net/blog/ > /dev/null
curl -fsS https://accidentalscientist.net/nem/ > /dev/null
curl -fsS https://accidentalscientist.net/nem/price-lab/ > /dev/null
curl -fsS https://accidentalscientist.net/nem/flow-trace/ > /dev/null
curl -fsS https://accidentalscientist.net/nem/charge-trace/ > /dev/null
curl -fsS https://accidentalscientist.net/stillpoint/ > /dev/null
curl -fsS https://accidentalscientist.net/pulse/ > /dev/null
curl -fsS https://accidentalscientist.net/life-compass/ > /dev/null
curl -fsS https://accidentalscientist.net/world-ledger/ > /dev/null
```

Then check in a real browser:

- the visible site version equals the release tag;
- navigation, dark mode, static assets, images, and responsive layout work;
- the homepage, one article, and every changed project render without console errors;
- authentication and user isolation still work if Life Compass changed;
- uploads are request-scoped if Portfolio Pulse changed;
- data currency and source dates are plausible on each analytical project; and
- contact delivery works if mail configuration changed.

For a contact or mail-routing release, verify both independent paths:

1. Send a direct message from an unrelated external account to `hello@accidentalscientist.net`; it must arrive through ImprovMX forwarding.
2. Submit the live website form with a valid name, external reply address, and recognizable test message; it must redirect to `/about/message-sent/`, reach the mailbox, show the website sender as `hello@accidentalscientist.net`, and preserve the visitor address as Reply-To.
3. Confirm the corresponding `Contact` database record exists. If notification delivery fails, the record must remain and the form must show the failure rather than redirecting to success.
4. Inspect the Gunicorn journal for a Resend acceptance identifier or a surfaced delivery error. Never paste the API key, private mailbox, or full environment file into verification evidence.

After verification, update the release-ledger row in `docs/DESIGN.md` with the deployed date, exact tag and commit, and verification result.

# 2. Production configuration

## 2.1 Required environment

The server `.env` contains secrets and must never be committed or copied into documentation. Required values include Django secret, allowed hosts, PostgreSQL connection values, email settings where enabled, and:

```text
DEBUG=False
STATIC_ROOT=/var/www/accidental-site/staticfiles
```

Article imports may override `ELITE_ARTICLES_DIR`. Contact delivery uses the Resend HTTPS API and requires `RESEND_API_KEY`, `CONTACT_EMAIL`, and `DEFAULT_FROM_EMAIL`; the API key should have sending-only access restricted to `accidentalscientist.net`, and the sender must belong to that verified domain. `RESEND_TIMEOUT_SECONDS` defaults to 10 seconds. The private mailbox stays in the forwarding provider rather than the application environment.

The production Droplet has 1 GB RAM and a persistent 2 GB `/swapfile` entry in `/etc/fstab`. Verify `swapon --show` and `free -h` after provisioning or recovery. Swap is only an emergency buffer: ChargeTrace deliberately processes catch-up ranges one operating day at a time, and heavy forecast work is performed sequentially rather than relying on swap as normal working memory.

Nginx must forward:

```nginx
proxy_set_header X-Forwarded-Proto $scheme;
```

Review `SECURE_SSL_REDIRECT`, HSTS, secure cookies, SSH policy, firewall, `fail2ban`, and admin protection through a lockout-safe procedure. Do not enable HSTS until HTTPS and proxy handling are verified.

## 2.2 Contact mail topology and recovery

Contact mail has two deliberately separate provider paths. Resend is not the inbox provider and ImprovMX is not the website's sending API.

| Concern | Provider and configuration | Required invariant |
|---|---|---|
| Direct incoming mail | Root-domain MX records point to `mx1.improvmx.com` at priority 10 and `mx2.improvmx.com` at priority 20; the `hello` alias forwards inside ImprovMX | Keep both root MX records. The private destination address exists only in ImprovMX. |
| Website-generated mail | Django posts to Resend over HTTPS using `RESEND_API_KEY`, with `DEFAULT_FROM_EMAIL` set to the public alias | Resend domain status is verified and receiving remains disabled. The Droplet does not depend on outbound SMTP. |
| Resend authentication | Provider-supplied DKIM TXT at `resend._domainkey`, plus SPF TXT and feedback MX scoped to the `send` subdomain | The `send`-subdomain MX is a return-path record; it must not replace the root ImprovMX MX records. Copy provider values exactly without recording them in this repository. |
| Recipient and reply path | `CONTACT_EMAIL` is the public alias; Resend sets Reply-To to the visitor's validated email address | A website notification routes back through ImprovMX, while Reply targets the visitor. General-purpose Gmail **Send mail as** is a separate capability and is not implied by this configuration. |
| DMARC and unrelated DNS | `_dmarc` and site-verification records remain independent of both providers | Do not remove unrelated TXT records while changing mail providers. Tighten DMARC only after authenticated mail has been monitored. |

An ImprovMX account-transfer TXT record proves domain ownership only during the transfer. Once the destination account reports the domain active, that temporary record can be removed; it does not deliver mail. The two root MX records are the records that must remain for forwarding.

Troubleshoot by separating the paths:

- If direct mail to the alias fails, inspect the root MX records, ImprovMX domain status, alias spelling, and forwarding destination.
- If the form saves a `Contact` but Resend rejects or times out, inspect the three application settings, verified-domain status, API-key scope, and Gunicorn logs.
- If Resend accepts a message but it is absent from the inbox, inspect ImprovMX forwarding activity and the mailbox spam folder before changing application code.
- If the public sender fails authentication, inspect DKIM and `send`-subdomain SPF/feedback records; do not point the root MX records at Resend as a repair.

The production `.env` must be owned by `thibault` with mode `600`. Remove obsolete Gmail SMTP variables after Resend is working, revoke superseded app passwords or provider keys, and rotate any credential exposed in a terminal capture. A temporary environment backup also contains secrets: protect it with mode `600`, retain it only through the verified rollback window, then remove it. Never display or screenshot the complete file.

## 2.3 Persistence and backups

| Data | Location | Backup implication |
|---|---|---|
| Django records and project datasets | PostgreSQL | Back up before migrations, bulk imports, backfills, registry changes, and destructive repair |
| Uploaded article/project images and StillPoint audio | `media/` | Requires filesystem or volume backup; it does not travel through Git |
| Static source and generated World Ledger JSON | Git working tree | Reproduced by the tagged release |
| Collected static files | `/var/www/accidental-site/staticfiles` | Rebuilt with `collectstatic`; not a primary backup |
| ChargeTrace source cache | `.battery_cache` on the server | Regenerable, but preserving it makes retries cheaper |
| NEM fuel source cache | `.nem_cache` on the server | Regenerable AEMO register and dispatch archives; preserve it to make retries and audits cheaper |
| Life Compass user state | PostgreSQL plus each browser's local mirror | PostgreSQL backup is authoritative for server persistence |

# 3. Ongoing data-management responsibilities

This section answers whether the site owner must do recurring work after deployment.

| Project | Owner action required? | Cadence | Current operating method | Consequence of a missed run |
|---|---|---|---|---|
| Portfolio and articles | Yes, when content changes | As needed | Import article packages; maintain project rows and media | New content is absent; existing content remains |
| NEM Dashboard suite | No routine upload; inspect the run result | Mondays at 09:00 Australia/Sydney | `refresh_nem_suite` catches up fuel and batteries, refreshes prices/weather and gas, and publishes the latest Sunday price origin | Views become stale; the gas rolling window becomes the binding recovery risk after several missed weekly runs |
| World Ledger | Yes only when deliberately revising the dataset | Manual, reviewed release | Generate locally, inspect the dataset diff, test, commit, and deploy | Existing Giga Dataset remains stable |
| StillPoint | Only when guided content changes | As needed | Upload an MP3 through admin | Existing guided audio remains |
| Portfolio Pulse | No | None | User CSVs are processed and discarded per request | No persistent dataset exists |
| Life Compass | No routine upload | Only when frontend code changes | Build from `personal_dashboard` and deploy compiled assets | Existing application and user data remain |

Until automated failure notifications are installed, the owner must inspect each scheduled run or the corresponding public freshness state every week.

## 3.1 Articles and portfolio records

Article source lives in `/home/thibault/elite-analytics-articles-2026` on production. Import is idempotent by slug:

```bash
sudo -u thibault git -C /home/thibault/elite-analytics-articles-2026 pull --ff-only origin main
sudo -u thibault bash -c 'cd /home/thibault/accidental-scientist-portfolio && venv/bin/python manage.py import_elite_articles --publish'
```

Before importing, confirm the article repository has no unpushed local packages. Project catalogue rows and categories are database content and must be maintained through Django admin or an intentional data migration. Media referenced by those rows must exist in the production media store.

## 3.2 NEM Dashboard fuel mix

Normal operation is direct AEMO ingestion:

```bash
venv/bin/python manage.py refresh_fuel_mix --cache-dir .nem_cache
```

The command uses AEMO's quarterly Generation Information workbook to map DUIDs to state and fuel, then integrates positive five-minute Dispatch SCADA into daily MWh. It targets the latest common safe date, currently two days behind wall-clock time, and refuses to publish a day when mapped positive generation falls below 95%. Set `NEM_GENERATION_REGISTER_URL` in the server `.env` when AEMO publishes a new quarterly workbook; no code or database migration is required.

The admin upload remains a reviewed repair fallback.

Upload CSV through **Admin → Nem dashboard → Fuel data uploads**. Required columns are:

```text
DateTime, State, Fuel Type, Supply
```

Review the upload summary, then verify the page's reporting window and units. Do not mix a manual file and a scheduler run for the same day without checking the replacement result.

## 3.3 Price Predictor Lab

The underlying sequence is:

```bash
cd /home/thibault/accidental-scientist-portfolio
venv/bin/python manage.py ingest_nem_prices
venv/bin/python manage.py ingest_nem_weather --kind observed --months 1
venv/bin/python manage.py ingest_nem_weather --kind forecast --months 1
venv/bin/python manage.py ingest_nem_weather --forward
venv/bin/python manage.py run_price_forecast
```

The unified command runs each Monday. Observed weather supplies settled history, recent archived issue-time forecasts fill the reanalysis tail, and the live forecast supplies the coming week. It publishes `run_price_forecast` only when a region is missing the most recent Sunday origin. Verify that the new origin exists, prior origins were not overwritten, and all six models for all six displayed regions have 336 forecast intervals.

`scikit-learn` remains isolated in `requirements-ml.txt`, but production installs that file because the scheduled forecast job publishes all six documented models. The web request path still serves stored rows and never trains a model.

For audit exports in a development or job environment:

```bash
python manage.py export_price_lab_data --region NSW1 --out ./price_lab_export
```

## 3.4 Gas Monitor

One-time initial production load:

```bash
cd /home/thibault/accidental-scientist-portfolio
venv/bin/python manage.py ingest_gbb_reference
venv/bin/python manage.py ingest_gbb_flows --archive
venv/bin/python manage.py ingest_gbb_flows --weekly
venv/bin/python manage.py check_gas_coverage
```

Manual incremental operation:

```bash
venv/bin/python manage.py ingest_gbb_flows
venv/bin/python manage.py check_gas_coverage --quiet
```

The unified Monday command passes `--weekly`, refreshing the slower reference tables before current flows, forecasts, linepack adequacy and missing submissions. Review the import summary and public Data currency table.

Flows and storage are retained for roughly 31 gas days in AEMO's current directory. A missed day is recoverable by the next run; a failure lasting roughly a month can require archive or local-file recovery. Use `--file` with one explicit `--report` only when replaying a reviewed local source. Backfills belong over SSH, not behind an admin request.

## 3.5 ChargeTrace

Initial registry and history setup:

```bash
cd /home/thibault/accidental-scientist-portfolio
venv/bin/python manage.py load_battery_registry --dry-run
venv/bin/python manage.py load_battery_registry
venv/bin/python manage.py refresh_battery_data --start 2026-07-01 --end 2026-08-08 --cache-dir .battery_cache
```

The dates above reproduce the documented validation window. For a later first production load, extend the end date only after verifying source availability and database capacity.

Manual incremental operation:

```bash
venv/bin/python manage.py refresh_battery_data --cache-dir .battery_cache
```

With no dates, the command starts after the latest stored summary and targets the latest common complete source date, normally two days behind wall-clock time. It processes one operating day at a time inside one audited range so a weekly catch-up has the same bounded memory peak as a daily repair. Verify the latest successful **Battery data refresh** admin row, source receipts, warnings, summary counts, page data-through date, and the displayed weekly freshness contract.

After changing calculation logic without changing source data:

```bash
venv/bin/python manage.py recalculate_battery_summaries
```

Registry changes require a reviewed JSON diff, a dry run, a database backup, a real load, and verification of affected historical and current assets.

## 3.6 World Ledger

World Ledger has no weekly production job. Build it in a reviewed development environment:

```powershell
venv\Scripts\python.exe manage.py refresh_world_lens_data
venv\Scripts\python.exe manage.py test world_lens
```

Inspect the generated `world_lens/data/world_lens.json` diff, cohort membership, source vintages, missingness, and ranking changes. Commit the reviewed JSON and deploy it with a site release. Do not regenerate it unreviewed on the production server.

## 3.7 StillPoint media

Upload guided meditation audio through **Admin → Stillpoint → Guided meditations**. Files must be MP3. Confirm media backup coverage and play the uploaded item from the public page.

## 3.8 Life Compass frontend handoff

The editable source lives in `personal_dashboard`, not this repository. When it changes:

1. Run `npm run build` in `personal_dashboard`.
2. Confirm Vite uses `base: "/static/life_compass/"`.
3. Copy the new hashed assets into `life_compass/static/life_compass/assets/`.
4. Update `index.html`, `strategy.html`, and `execution.html` to reference the new hashes.
5. Verify every new reference exists before removing any stale asset.
6. Run Django tests and browser-check public and authenticated modes.

Do not delete hashed assets through an unresolved glob or from outside the verified Life Compass asset directory.

# 4. Scheduler setup and verification

Use the single timezone-aware persistent systemd timer supplied in `nem_dashboard/deploy/`. The suite command runs its source families sequentially, continues attempting later sources after a failure, and exits non-zero with a combined failure summary so the journal tells the whole story.

| Job | Intended schedule | Command |
|---|---|---|
| NEM Dashboard suite | Monday 09:00 Australia/Sydney | `refresh_nem_suite` |

Install and activate it as a server administrator:

```bash
cd /home/thibault/accidental-scientist-portfolio
sudo -u thibault venv/bin/python manage.py refresh_nem_suite

# Prevent the retired gas-only timer from duplicating one stage of the suite.
sudo systemctl disable --now gas-refresh.timer 2>/dev/null || true
sudo cp nem_dashboard/deploy/nem-suite-refresh.service /etc/systemd/system/
sudo cp nem_dashboard/deploy/nem-suite-refresh.timer /etc/systemd/system/
sudo systemctl daemon-reload

systemd-analyze calendar 'Mon *-*-* 09:00:00 Australia/Sydney'
sudo systemctl enable --now nem-suite-refresh.timer
systemctl list-timers nem-suite-refresh.timer --all
```

After the first automatic run:

```bash
systemctl status nem-suite-refresh.timer --no-pager
systemctl status nem-suite-refresh.service --no-pager
journalctl -u nem-suite-refresh.service --since '24 hours ago' --no-pager
```

For every service and timer:

1. run the unified command manually as `thibault` first;
2. use the project virtual environment and working directory;
3. set `Persistent=true` so a missed boot-time run is caught up;
4. set the Australia/Sydney timezone explicitly and validate with `systemd-analyze calendar`;
5. send stdout and stderr to the journal;
6. confirm `systemctl list-timers` shows the next Monday 09:00 Australia/Sydney run; and
7. inspect `journalctl -u <service>` plus the application's refresh record after the first automatic run.

Do not call a scheduler active merely because unit files exist. It becomes active only after the timer is enabled, its next run is visible, and one automatic execution has succeeded.

# 5. Rollback and recovery

## 5.1 Code-only rollback

Identify the previous verified tag. Do not use `git reset --hard` as the routine production rollback because it destroys local state and obscures which release is running.

```bash
sudo -u thibault git -C /home/thibault/accidental-scientist-portfolio fetch --tags
sudo -u thibault git -C /home/thibault/accidental-scientist-portfolio switch --detach v2.7.3
sudo -u thibault /home/thibault/accidental-scientist-portfolio/venv/bin/pip install -r /home/thibault/accidental-scientist-portfolio/requirements.txt
sudo chown -R thibault:www-data /var/www/accidental-site/staticfiles
sudo -u thibault bash -c 'cd /home/thibault/accidental-scientist-portfolio && venv/bin/python manage.py collectstatic --noinput'
sudo systemctl restart gunicorn
```

Replace the tag with the verified rollback target and repeat the smoke tests. The next normal deployment returns the checkout to `main`.

## 5.2 Migration or data rollback

Do not automatically run `migrate` after checking out older code. A code rollback is safe only when the existing schema remains compatible. If the failed release changed schema or transformed data:

1. stop writes if continued use could worsen the damage;
2. identify the exact migration and whether it is reversible;
3. prefer restoring the pre-release database snapshot when data were transformed;
4. reverse a migration only after reviewing its operations against the current data; and
5. verify application, dataset, and media consistency before reopening.

Bulk data refreshes are normally idempotent. Repair by re-running the reviewed date or source where possible; restore backup only when the operation deleted or irreversibly transformed data.

# 6. Recurring problems

- **Static collection permission denied:** restore `thibault:www-data` ownership on `/var/www/accidental-site/staticfiles`, then rerun `collectstatic`.
- **Wrong server directory:** only `/home/thibault/accidental-scientist-portfolio` is served.
- **Git dubious ownership:** configure the exact served repository as a safe directory once; do not use a broad wildcard.
- **Version mismatch:** production must resolve to the intended tag and the rendered version must match it.
- **Stale analytical page:** inspect the project refresh record, command journal, source availability, and public currency label before changing data manually.
- **Failed current-window gas refresh:** run coverage first; use archive or reviewed `--file` recovery if the retained source window has elapsed.
- **ChargeTrace partial day:** retain visible warnings, inspect source receipts and registry expectations, and do not clip or invent missing storage observations.
