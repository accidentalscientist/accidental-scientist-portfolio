"""Refresh the gas time series: flows, forecasts, linepack flags, non-submissions.

    # the Monday morning refresh: everything, in dependency order
    python manage.py ingest_gbb_flows --weekly

    # time series only, leaving the registry alone
    python manage.py ingest_gbb_flows

    # one report
    python manage.py ingest_gbb_flows --report linepack_adequacy

    # replay a file downloaded by hand
    python manage.py ingest_gbb_flows --report flows --file ./GasBBActualFlowStorageLast31.CSV

The actual-flow file is a ROLLING 31-DAY WINDOW. A skipped refresh is not
staleness, it is data loss, so this command reports how much margin is
left after every run rather than leaving that for someone to work out.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...constants import ARCHIVE_REPORTS
from ...ingest import IngestError
from ...services import (
    TIME_SERIES_ORDER, WEEKLY_ORDER, coverage_report, gas_day_gaps,
    ingest_archive, ingest_report, ingest_reports, summarise,
)


class Command(BaseCommand):
    help = 'Ingest Gas Bulletin Board flow, forecast and constraint reports.'

    def add_arguments(self, parser):
        parser.add_argument('--report', choices=sorted(set(TIME_SERIES_ORDER) | set(ARCHIVE_REPORTS)),
                            action='append',
                            help='Report to refresh. Repeatable. Defaults to all time series, '
                                 'or to every archive when --archive is given.')
        parser.add_argument('--weekly', action='store_true',
                            help='Refresh the registry as well, in dependency order.')
        parser.add_argument('--archive', action='store_true',
                            help=f'One-time backfill from the full-history zip. '
                                 f'Available for: {", ".join(sorted(ARCHIVE_REPORTS))}.')
        parser.add_argument('--file', help='Parse a local CSV instead of fetching. Requires a single --report.')

    def handle(self, *args, **options):
        if options['archive']:
            return self._backfill(options['report'] or sorted(ARCHIVE_REPORTS))

        if options['file']:
            reports = options['report']
            if not reports or len(reports) != 1:
                raise CommandError('--file needs exactly one --report so the parser is unambiguous.')
            path = Path(options['file']).expanduser()
            if not path.exists():
                raise CommandError(f'no such file: {path}')
            try:
                report = ingest_report(reports[0],
                                       text=path.read_text(encoding='utf-8-sig', errors='replace'))
            except IngestError as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(summarise([report]))
            return

        if options['weekly']:
            keys = WEEKLY_ORDER
        else:
            keys = options['report'] or TIME_SERIES_ORDER
            # `nameplate` is reachable here only via --archive; refreshing
            # the current-ratings file is the reference command's job.
            keys = [k for k in keys if k in TIME_SERIES_ORDER]
            if not keys:
                raise CommandError('nothing to refresh; did you mean --archive?')

        results = ingest_reports(keys)
        self.stdout.write(summarise(results))

        failed = [r['report'] for r in results if r.get('error')]
        stored = sum(r.get('stored', 0) for r in results)

        if failed:
            self.stdout.write(self.style.WARNING(
                f"Stored {stored} rows. Failed reports: {', '.join(failed)}."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(f'Stored {stored} rows across {len(results)} reports.'))

        self._report_margin()

    def _backfill(self, reports):
        """Load the full-history archives. Minutes, not seconds."""
        unknown = [r for r in reports if r not in ARCHIVE_REPORTS]
        if unknown:
            raise CommandError(f"no archive for: {', '.join(unknown)}. "
                               f"Available: {', '.join(sorted(ARCHIVE_REPORTS))}.")

        for key in reports:
            self.stdout.write(f'{key}: downloading archive…')
            try:
                report = ingest_archive(key, progress=self._progress)
            except IngestError as exc:
                self.stdout.write(self.style.ERROR(f'{key}: FAILED — {exc}'))
                continue
            self.stdout.write('')
            self.stdout.write(summarise([report]))

        self._report_margin()

    def _progress(self, done, total, stored):
        # Overwrite one line rather than scrolling: a backfill is 20+ chunks
        # and the useful information is the current position, not the trail.
        self.stdout.write(f'\r  {min(done, total):,} / {total:,} rows parsed, '
                          f'{stored:,} stored', ending='')
        self.stdout.flush()

    def _report_margin(self):
        """Say how long the next refresh can be left, in plain days.

        The whole point of stating this after every run is that the
        operator never has to remember the window length; the command
        derives it from the sources.
        """
        gaps = gas_day_gaps()
        if gaps:
            shown = ', '.join(str(day) for day in gaps[:5])
            more = f' and {len(gaps) - 5} more' if len(gaps) > 5 else ''
            self.stdout.write(self.style.WARNING(f'Missing gas days: {shown}{more}.'))

        for row in coverage_report():
            if not row['loses_data_if_skipped'] or row['days_until_loss'] is None:
                continue
            margin = row['days_until_loss']
            message = (f"{row['source']}: current to {row['latest_gas_date']}, "
                       f"{margin} days before the window drops data.")
            if margin <= 7:
                self.stdout.write(self.style.ERROR(message + ' Refresh now.'))
            elif margin <= 14:
                self.stdout.write(self.style.WARNING(message))
            else:
                self.stdout.write(message)
