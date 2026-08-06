"""Produce and store the week-ahead forecast for each region.

This is the Sunday command. It fits the temperature coefficients on history
up to the origin, runs all three models, and writes the results away without
touching any earlier run. Last week's predictions stay exactly as they were
published, which is what makes the following week's review meaningful.

    # the normal weekly call: origin is the Sunday just gone
    python manage.py run_price_forecast

    # re-run a past origin to check the archive reproduces
    python manage.py run_price_forecast --origin 2026-07-26

    # walk the last 12 weeks to build a backtest record
    python manage.py run_price_forecast --backfill-weeks 12
"""

from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ...constants import DISPLAY_REGIONS, INTERVALS_PER_DAY, NEM_TZ
from ...forecasting import MODEL_LABELS
from ...services import available_regions, generate_and_save, most_recent_sunday, review_origin


class Command(BaseCommand):
    help = 'Fit and store the week-ahead price forecasts for each NEM region.'

    def add_arguments(self, parser):
        # Includes NEM: the derived market-wide series is forecast exactly
        # like any settled region.
        parser.add_argument('--region', choices=DISPLAY_REGIONS, action='append',
                            help='Region to forecast. Repeatable. Defaults to every region holding data.')
        parser.add_argument('--origin', help='Forecast origin as YYYY-MM-DD. Defaults to the most recent Sunday.')
        parser.add_argument('--horizon-days', type=int, default=7)
        parser.add_argument('--training-weeks', type=int, default=52,
                            help='How much history the temperature fit may see.')
        parser.add_argument('--backfill-weeks', type=int, default=0,
                            help='Also run this many earlier weekly origins, to build a backtest record.')

    def handle(self, *args, **options):
        regions = options['region'] or available_regions()
        if not regions:
            raise CommandError('no price data loaded yet; run ingest_nem_prices first')

        origin = self._resolve_origin(options['origin'])
        origins = [origin - timedelta(weeks=w) for w in range(options['backfill_weeks'] + 1)]

        for run_origin in sorted(origins):
            self.stdout.write(self.style.MIGRATE_HEADING(f'Origin {run_origin:%Y-%m-%d %H:%M} (NEM time)'))
            for region in regions:
                runs = generate_and_save(
                    region, run_origin,
                    horizon_days=options['horizon_days'],
                    training_weeks=options['training_weeks'],
                )
                for run in runs:
                    count = run.points.count()
                    flag = '' if run.is_leakage_safe else '  [observed-temperature fallback]'
                    self.stdout.write(
                        f'  {region:5} {MODEL_LABELS.get(run.model_key, run.model_key):24} '
                        f'{count:4} intervals{flag}'
                    )

                self._report_review(region, run_origin)

        self.stdout.write(self.style.SUCCESS('Done.'))

    def _resolve_origin(self, raw):
        if not raw:
            return most_recent_sunday(timezone.now())
        try:
            parsed = datetime.strptime(raw, '%Y-%m-%d')
        except ValueError as exc:
            raise CommandError('--origin must be YYYY-MM-DD') from exc
        return parsed.replace(tzinfo=NEM_TZ)

    def _report_review(self, region, origin):
        """Print how this origin scored, when the actuals already exist."""
        for entry in review_origin(region, origin):
            result = entry['score']
            if not result:
                continue

            # A week still in progress is scored on whatever has settled, so
            # say how many intervals that was. Otherwise a four-day score
            # reads exactly like a finished one.
            expected = entry['run'].horizon_days * INTERVALS_PER_DAY
            partial = '' if result['intervals'] >= expected else (
                f"  [partial: {result['intervals']}/{expected}]"
            )
            skill = entry['skill']
            skill_text = '' if skill is None else f'  skill {skill:+.1%}'
            self.stdout.write(
                f"    scored {entry['label']:24} MAE ${result['mae']:8.2f}  "
                f"median ${result['medae']:7.2f}{skill_text}{partial}"
            )
