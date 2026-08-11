from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from django.test import SimpleTestCase

from nem_battery_explorer.management.commands.refresh_battery_data import Command


class RefreshBatteryCommandTests(SimpleTestCase):
    @patch('nem_battery_explorer.management.commands.refresh_battery_data.refresh_range')
    @patch('nem_battery_explorer.management.commands.refresh_battery_data.download_source_set')
    def test_range_is_processed_one_operating_day_at_a_time(self, download, refresh):
        def source_set(start_date, end_date, cache_dir):
            self.assertEqual(start_date, end_date)
            return {
                'next_day': {},
                'prices': {},
                'scada': {},
                'receipts': [{
                    'source': 'dispatchis',
                    'operating_date': start_date.isoformat(),
                    'filename': f'{start_date}.zip',
                }],
            }

        download.side_effect = source_set
        run = SimpleNamespace(source_receipts=[], save=Mock())
        processed_days = []
        warnings = []
        cache_dir = Path('.battery_cache')

        Command()._run(
            date(2026, 8, 1),
            date(2026, 8, 3),
            cache_dir,
            run,
            processed_days,
            warnings,
        )

        expected_dates = [date(2026, 8, day) for day in range(1, 4)]
        self.assertEqual(
            download.call_args_list,
            [call(day, day, cache_dir) for day in expected_dates],
        )
        self.assertEqual(
            [(args[0], args[1]) for args, _ in refresh.call_args_list],
            [(day, day) for day in expected_dates],
        )
        self.assertEqual(len(run.source_receipts), 3)
        self.assertEqual(run.save.call_count, 3)
