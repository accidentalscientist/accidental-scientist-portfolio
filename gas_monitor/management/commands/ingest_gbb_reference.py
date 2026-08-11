"""Refresh the static system model from the AEMO Gas Bulletin Board.

The sources are unauthenticated HTTP GETs, so scheduling this command is
the entire difference between a manual refresh and an automated one.
Nothing about the code needs to change.

    # everything: basins, locations, facilities, points, zones, capacity
    python manage.py ingest_gbb_reference

    # one report only
    python manage.py ingest_gbb_reference --report facilities

    # a file already downloaded by hand, when the network is the problem
    python manage.py ingest_gbb_reference --report facilities --file ./GasBBFacilities.CSV
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...ingest import IngestError
from ...services import REFERENCE_ORDER, ingest_reference, ingest_reference_report, summarise


class Command(BaseCommand):
    help = 'Ingest the Gas Bulletin Board reference reports into the static system model.'

    def add_arguments(self, parser):
        parser.add_argument('--report', choices=REFERENCE_ORDER, action='append',
                            help='Report to refresh. Repeatable. Defaults to all, in dependency order.')
        parser.add_argument('--file', help='Parse a local CSV instead of fetching. Requires a single --report.')

    def handle(self, *args, **options):
        reports = options['report']

        if options['file']:
            if not reports or len(reports) != 1:
                raise CommandError('--file needs exactly one --report so the parser is unambiguous.')
            path = Path(options['file']).expanduser()
            if not path.exists():
                raise CommandError(f'no such file: {path}')
            try:
                report = ingest_reference_report(reports[0],
                                                 text=path.read_text(encoding='utf-8-sig', errors='replace'))
            except IngestError as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(summarise([report]))
            return

        results = ingest_reference(reports)
        self.stdout.write(summarise(results))

        failed = [r['report'] for r in results if r.get('error')]
        stored = sum(r.get('stored', 0) for r in results)

        if failed:
            # A partial refresh is a real outcome, not a crash: a nameplate
            # fetch failing should not cost the facility registry that just
            # updated. Report it loudly and leave what succeeded in place.
            self.stdout.write(self.style.WARNING(
                f"Stored {stored} rows. Failed reports: {', '.join(failed)}."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(f'Stored {stored} rows across {len(results)} reports.'))
