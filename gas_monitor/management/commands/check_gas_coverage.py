"""Report how current the gas data is, and whether anything is missing.

Writes nothing. Safe to run any time, and the intended answer to "is the
Monday refresh still happening?"

    python manage.py check_gas_coverage

Exits non-zero when a backward-looking window is within a week of dropping
data, so a scheduler or a CI step can treat it as a failure rather than
needing someone to read the output.
"""

import sys

from django.core.management.base import BaseCommand

from ...services import coverage_report, gas_day_gaps

URGENT_DAYS = 7


class Command(BaseCommand):
    help = 'Report gas data coverage, gaps, and how long before a rolling window drops data.'

    def add_arguments(self, parser):
        parser.add_argument('--quiet', action='store_true',
                            help='Print only problems.')

    def handle(self, *args, **options):
        rows = coverage_report()
        if not rows:
            self.stdout.write(self.style.WARNING('No gas data has been ingested yet.'))
            return

        urgent = False

        for row in rows:
            if row['days_behind'] is not None:
                position = f"{row['days_behind']}d behind"
            elif row['days_ahead'] is not None:
                position = f"{row['days_ahead']}d ahead"
            else:
                position = 'no gas days held'
            line = (f"{row['source']:20} {row['earliest_gas_date']} to {row['latest_gas_date']} "
                    f"({position}), last run {row['last_run_at']:%Y-%m-%d %H:%M}")

            if row['loses_data_if_skipped'] and row['days_until_loss'] is not None:
                margin = row['days_until_loss']
                line += f", {margin}d margin"
                if margin <= URGENT_DAYS:
                    urgent = True
                    self.stdout.write(self.style.ERROR(line))
                    continue
                if margin <= URGENT_DAYS * 2:
                    self.stdout.write(self.style.WARNING(line))
                    continue

            if not options['quiet']:
                self.stdout.write(line)

        gaps = gas_day_gaps()
        if gaps:
            urgent = True
            shown = ', '.join(str(day) for day in gaps[:10])
            more = f' and {len(gaps) - 10} more' if len(gaps) > 10 else ''
            self.stdout.write(self.style.ERROR(f'Missing gas days in the flow record: {shown}{more}.'))
        elif not options['quiet']:
            self.stdout.write(self.style.SUCCESS('No gaps in the flow record.'))

        if urgent:
            sys.exit(1)
