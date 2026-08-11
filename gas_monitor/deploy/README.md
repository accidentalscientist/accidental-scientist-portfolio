# Weekly refresh: install on the droplet

Runs `ingest_gbb_flows --weekly` then `check_gas_coverage` every **Monday
at 09:00 Australia/Sydney**, which is the cadence the page states.

## Install

```bash
sudo cp /home/thibault/accidental-scientist-portfolio/gas_monitor/deploy/gas-refresh.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gas-refresh.timer
```

## Verify

```bash
systemctl list-timers gas-refresh.timer     # next run
sudo systemctl start gas-refresh.service    # run it now, once
journalctl -u gas-refresh.service -n 40     # what it did
```

A successful run ends with a line like:

```
flows: current to 2026-08-09, 30 days before the window drops data.
```

## Why the timer matters more here than elsewhere on the site

The actual-flow report is a **31-day rolling window**. Data that falls out
of it is gone from AEMO's current directory, recoverable only from the
archive. The Price Predictor Lab tolerates a missed Sunday because its
AEMO file is cumulative within the month; this does not.

A Monday refresh carries roughly 30 days of margin. Three consecutive
Mondays can be missed and the fourth run still catches every gas day; miss
four and days are lost.

`check_gas_coverage` **exits non-zero** when a backward window is within a
week of dropping data, so the unit shows as failed rather than quietly
succeeding. `systemctl --failed` is therefore a real health check.

## If the timer stops

Nothing silently breaks — the public page renders its own currency in the
release bar at the top, so a stalled refresh is visible to any reader.
That is the alerting.

To catch up after a long outage, use the archive path rather than waiting
for the weekly window:

```bash
sudo -u thibault bash -c 'cd /home/thibault/accidental-scientist-portfolio && venv/bin/python manage.py ingest_gbb_flows --archive'
```

## Timezone

`OnCalendar` is wall-clock, and the droplet runs Australia/Sydney. That is
deliberate: the intent is "Monday morning for the operator", and pinning
it to UTC would drift an hour either side of daylight saving. Confirm with
`timedatectl` if the server is ever rebuilt.
