"""Tests for the static system model.

Fixtures are trimmed copies of real Bulletin Board rows, including the
inconsistencies that matter: mixed date formats, lower-case headers in the
nameplate report only, and the -1 sentinel the source uses for "no
location".
"""

from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from . import ingest, services
from .models import (
    ConnectionPoint, Facility, FlowForecast, FlowObservation, LinepackAdequacy,
    LinepackZone, Location, MissingSubmission, NameplateRating,
)

FACILITIES_CSV = (
    'FacilityName,FacilityShortName,FacilityId,FacilityType,FacilityTypeDescription,'
    'OperatingState,OperatingStateDate,OperatorName,OperatorId,OperatorChangeDate\n'
    'Adelaide Brighton,,555091,BBLARGE,BB Large,ACTIVE,2023/05/25,Adelaide Brighton Cement Limited,150,2023/05/25\n'
    'Moomba,,540001,PROD,Production,ACTIVE,2018/05/01,Santos,88,2018/05/01\n'
    'VTS,,530110,PIPE,BB pipeline,ACTIVE,2018/05/01,APA Group,94,2018/05/01\n'
    'Old Plant,,999999,PROD,Production,INACTIVE,2020/01/01,Nobody,1,2020/01/01\n'
)

LOCATIONS_CSV = (
    'LocationName,LocationId,LocationType,State,Description,LastUpdated\n'
    'Adelaide,550016,STANDARD,SA,Connections within Adelaide,2018/05/01 00:00:00\n'
    'Wallumbilla Hub,540032,HUB,QLD,APA Wallumbilla Hub,2018/07/01 00:00:00\n'
)

CONNECTION_POINTS_CSV = (
    'FacilityName,FacilityId,FacilityType,ConnectionPointId,ConnectionPointName,FlowDirection,'
    'Exempt,ExemptionDescription,NodeId,StateId,StateName,LocationName,LocationId,LastUpdated\n'
    'Adelaide Brighton,555091,BBLARGE,1590045,Adelaide Brighton,RECEIPT,FALSE,,99215,5,South Australia,Adelaide,550016,2023/05/23 14:06:43\n'
    'VTS,530110,PIPE,1590046,VTS Point A,DELIVERY,FALSE,,99216,2,Victoria,Unknown,-1,2023/05/23 14:06:43\n'
    'Ghost,404404,PIPE,1590047,Orphan Point,DELIVERY,FALSE,,99217,2,Victoria,Nowhere,550016,2023/05/23 14:06:43\n'
)

NAMEPLATE_CSV = (
    'facilityname,facilityid,facilitytype,capacitytype,receiptlocation,ReceiptLocationName,'
    'deliverylocation,DeliveryLocationName,capacitydescription,flowdirection,capacityquantity,'
    'effectivedate,description,LastUpdated\n'
    'VTS,530110,PIPE,MDQ,1305053,Athena Receipt,1305059,SWP Delivery,West to East,NONE,400.000,'
    '04 Feb 2026 00:00:00,Initial rating,2026/02/04 15:29:02\n'
    'VTS,530110,PIPE,MDQ,1305058,SWP Receipt,1305054,Athena Delivery,East to West,NONE,400.000,'
    '04 Feb 2026 00:00:00,Initial rating,2026/02/04 15:29:02\n'
    'Moomba,540001,PROD,MDQ,-1,,-1,,,NONE,20.000,29 Aug 2019 00:00:00,,2019/08/29 16:17:08\n'
)

LINEPACK_CSV = (
    'Operator,LinepackZone,LinepackZoneDescription\n'
    'APA Group,AGP-LP-01,The entirety of the Amadeus Gas Pipeline.\n'
    'APA Group,AGP-LP-01,Duplicate row for a second segment.\n'
    'APA Group,VTS-LP-01,Victorian Transmission System.\n'
)

DEMAND_ZONES_CSV = (
    'FacilityName,FacilityType,FacilityId,NodeId,ConnectionPointId,FlowDirection,'
    'ConnectionPointName,State,DemandZone\n'
    'VTS,PIPE,530110,99216,1590046,DELIVERY,VTS Point A,VIC,VTS-DE-01\n'
    'Nothing,PIPE,404404,99217,1590047,DELIVERY,Orphan Point,VIC,GHOST-DE-01\n'
)

BASINS_CSV = 'BasinId,BasinName\n10000,Surat\n10007,Cooper-Eromanga\n'


class DateParsingTests(TestCase):
    """The Bulletin Board serves several date formats from one directory."""

    def test_accepts_every_observed_format(self):
        for raw in ('2023/05/25', '2019/08/29 16:17:08', '29 Aug 2019 00:00:00',
                    '07 Aug 2026 11:13:31', '2026-08-06'):
            self.assertIsNotNone(ingest.parse_gbb_datetime(raw), raw)

    def test_unparseable_returns_none_rather_than_raising(self):
        self.assertIsNone(ingest.parse_gbb_datetime('not a date'))
        self.assertIsNone(ingest.parse_gbb_datetime(''))
        self.assertIsNone(ingest.parse_gbb_datetime(None))

    def test_timestamps_are_market_time_not_local_time(self):
        parsed = ingest.parse_gbb_datetime('2026/08/06 12:00:00')
        self.assertEqual(parsed.utcoffset().total_seconds(), 10 * 3600)


class ParsingTests(TestCase):

    def test_missing_columns_are_rejected_before_any_row_is_trusted(self):
        with self.assertRaises(ingest.IngestError):
            ingest.parse_facilities('Nope,Wrong\n1,2\n')

    def test_nameplate_header_is_case_normalised(self):
        """This report alone publishes lower-case column names."""
        rows, report = ingest.parse_nameplate(NAMEPLATE_CSV)
        self.assertEqual(report['parsed'], 3)
        self.assertEqual(rows[0]['capacity_tj'], 400.0)

    def test_facilities_parse_with_operating_state(self):
        rows, report = ingest.parse_facilities(FACILITIES_CSV)
        self.assertEqual(report['parsed'], 4)
        self.assertEqual(report['skipped'], 0)
        self.assertEqual(rows[0]['operator_name'], 'Adelaide Brighton Cement Limited')

    def test_connection_point_minus_one_location_becomes_null(self):
        """-1 is the source's 'not applicable', not a location id."""
        rows, _ = ingest.parse_connection_points(CONNECTION_POINTS_CSV)
        vts = next(r for r in rows if r['connection_point_id'] == 1590046)
        self.assertIsNone(vts['location_id'])


class StorageTests(TestCase):

    def _load_core(self):
        services.ingest_reference_report('locations', text=LOCATIONS_CSV)
        services.ingest_reference_report('facilities', text=FACILITIES_CSV)

    def test_ingest_is_idempotent(self):
        """Running twice must refresh, never duplicate."""
        for _ in range(2):
            self._load_core()
            services.ingest_reference_report('connection_points', text=CONNECTION_POINTS_CSV)
            services.ingest_reference_report('nameplate', text=NAMEPLATE_CSV)

        self.assertEqual(Facility.objects.count(), 4)
        self.assertEqual(Location.objects.count(), 2)
        self.assertEqual(NameplateRating.objects.count(), 3)

    def test_bidirectional_pipeline_keeps_both_legs(self):
        """Two legs at the same capacity are reverse haul, not a duplicate."""
        self._load_core()
        services.ingest_reference_report('nameplate', text=NAMEPLATE_CSV)
        vts_legs = NameplateRating.objects.filter(facility_id=530110)
        self.assertEqual(vts_legs.count(), 2)
        self.assertEqual({leg.receipt_location_id for leg in vts_legs}, {1305053, 1305058})

    def test_connection_point_without_its_facility_is_reported_not_dropped_silently(self):
        self._load_core()
        report = services.ingest_reference_report('connection_points', text=CONNECTION_POINTS_CSV)
        self.assertEqual(report['stored'], 2)
        self.assertEqual(report['orphaned'], 1)
        self.assertFalse(ConnectionPoint.objects.filter(connection_point_id=1590047).exists())

    def test_linepack_zones_collapse_on_code(self):
        report = services.ingest_reference_report('linepack_zones', text=LINEPACK_CSV)
        self.assertEqual(report['stored'], 2)
        self.assertEqual(LinepackZone.objects.count(), 2)

    def test_demand_zones_annotate_existing_points_only(self):
        self._load_core()
        services.ingest_reference_report('connection_points', text=CONNECTION_POINTS_CSV)
        report = services.ingest_reference_report('demand_zones', text=DEMAND_ZONES_CSV)
        self.assertEqual(report['stored'], 1)
        self.assertEqual(report['orphaned'], 1)
        self.assertEqual(ConnectionPoint.objects.get(connection_point_id=1590046).demand_zone,
                         'VTS-DE-01')

    def test_summary_counts_active_separately(self):
        self._load_core()
        summary = services.system_model_summary()
        production = next(r for r in summary['by_type'] if r['code'] == 'PROD')
        self.assertEqual(production['total'], 2)
        self.assertEqual(production['active'], 1)

    def test_summary_is_none_when_nothing_ingested(self):
        self.assertIsNone(services.system_model_summary())


FLOWS_CSV = (
    'GasDate,FacilityName,FacilityId,FacilityType,Demand,Supply,TransferIn,TransferOut,'
    'HeldInStorage,CushionGasStorage,State,LocationName,LocationId,LastUpdated\n'
    # One facility, two locations, same gas day: the fan-out the natural key exists for.
    '2026/08/06,VTS,530110,PIPE,407.098,0.000,0.000,12.000,,,VIC,Adelaide,550016,2026/08/07 11:00:00\n'
    '2026/08/06,VTS,530110,PIPE,100.000,0.000,0.000,3.000,,,VIC,Wallumbilla Hub,540032,2026/08/07 11:00:00\n'
    '2026/08/06,Moomba,540001,PROD,0.000,402.000,0.000,0.000,,,SA,Adelaide,550016,2026/08/07 11:00:00\n'
    '2026/08/06,Adelaide Brighton,555091,BBLARGE,0.320,0.000,0.000,0.000,,,SA,Adelaide,550016,2026/08/07 11:00:00\n'
    '2026/08/05,VTS,530110,PIPE,390.000,0.000,0.000,10.000,,,VIC,Adelaide,550016,2026/08/06 11:00:00\n'
)

# The same gas day and facility restated LATER, with a different quantity.
FLOWS_REVISED_CSV = (
    'GasDate,FacilityName,FacilityId,FacilityType,Demand,Supply,TransferIn,TransferOut,'
    'HeldInStorage,CushionGasStorage,State,LocationName,LocationId,LastUpdated\n'
    '2026/08/06,VTS,530110,PIPE,999.000,0.000,0.000,12.000,,,VIC,Adelaide,550016,2026/08/09 09:00:00\n'
)

# The same key again, but stamped EARLIER than what is already stored.
FLOWS_STALE_CSV = (
    'GasDate,FacilityName,FacilityId,FacilityType,Demand,Supply,TransferIn,TransferOut,'
    'HeldInStorage,CushionGasStorage,State,LocationName,LocationId,LastUpdated\n'
    '2026/08/06,VTS,530110,PIPE,1.000,0.000,0.000,0.000,,,VIC,Adelaide,550016,2026/08/01 09:00:00\n'
)

STORAGE_FLOWS_CSV = (
    'GasDate,FacilityName,FacilityId,FacilityType,Demand,Supply,TransferIn,TransferOut,'
    'HeldInStorage,CushionGasStorage,State,LocationName,LocationId,LastUpdated\n'
    '2026/08/06,Iona UGS,530012,STOR,16.100,175.900,0.000,0.000,14474.300,,VIC,Adelaide,550016,'
    '2026/08/07 11:00:00\n'
)

LCA_CSV = (
    'FacilityName,FacilityId,FacilityType,GasDate,Flag,Description,LastUpdated\n'
    'VTS,530110,PIPE,07 Aug 2026 15:15:00,GREEN,,07 Aug 2026 11:13:31\n'
    'VTS,530110,PIPE,08 Aug 2026 15:15:00,AMBER,Tight,07 Aug 2026 11:13:31\n'
)

MISSING_CSV = (
    'GasDate,FacilityName,FacilityId,ConnectionPointId\n'
    '06 Aug 2026 00:00:00,Adelaide Brighton,555091,-1\n'
)

FORECASTS_CSV = (
    'Gasdate,FacilityId,FacilityName,FacilityType,LocationId,LocationName,State,'
    'Demand,Supply,TransferIn,TransferOut,LastUpdated\n'
    '2026/08/12,530110,VTS,PIPE,550016,Adelaide,VIC,410.000,0.000,0.000,11.000,2026/08/10 12:00:00\n'
)


class TimeSeriesTests(TestCase):

    def setUp(self):
        services.ingest_reference_report('locations', text=LOCATIONS_CSV)
        services.ingest_reference_report('facilities', text=FACILITIES_CSV)
        # Storage and Iona are not in the shared facility fixture.
        Facility.objects.create(facility_id=530012, name='Iona UGS', facility_type='STOR',
                                operating_state='ACTIVE')

    def test_one_facility_reporting_at_two_locations_keeps_both_rows(self):
        """The natural key is (gas day, facility, location), not (gas day, facility)."""
        report = services.ingest_report('flows', text=FLOWS_CSV)
        self.assertEqual(report['stored'], 5)
        vts_on_the_6th = FlowObservation.objects.filter(gas_date=date(2026, 8, 6),
                                                        facility_id=530110)
        self.assertEqual(vts_on_the_6th.count(), 2)

    def test_reingesting_the_same_file_does_not_duplicate(self):
        services.ingest_report('flows', text=FLOWS_CSV)
        services.ingest_report('flows', text=FLOWS_CSV)
        self.assertEqual(FlowObservation.objects.count(), 5)

    def test_a_newer_revision_overwrites(self):
        services.ingest_report('flows', text=FLOWS_CSV)
        services.ingest_report('flows', text=FLOWS_REVISED_CSV)
        row = FlowObservation.objects.get(gas_date=date(2026, 8, 6), facility_id=530110,
                                          location_id=550016)
        self.assertEqual(row.demand_tj, 999.0)

    def test_an_older_row_cannot_clobber_a_newer_one(self):
        """Backfill running after an incremental must not undo it."""
        services.ingest_report('flows', text=FLOWS_CSV)
        report = services.ingest_report('flows', text=FLOWS_STALE_CSV)

        self.assertEqual(report['superseded'], 1)
        self.assertEqual(report['stored'], 0)
        row = FlowObservation.objects.get(gas_date=date(2026, 8, 6), facility_id=530110,
                                          location_id=550016)
        self.assertEqual(row.demand_tj, 407.098)

    def test_blank_storage_is_null_not_zero(self):
        """Null means 'does not store gas'. Zero would be a claim."""
        services.ingest_report('flows', text=FLOWS_CSV)
        pipe = FlowObservation.objects.get(gas_date=date(2026, 8, 6), facility_id=530110,
                                           location_id=550016)
        self.assertIsNone(pipe.held_in_storage_tj)

    def test_storage_withdrawal_reads_as_negative_net(self):
        services.ingest_report('flows', text=STORAGE_FLOWS_CSV)
        iona = FlowObservation.objects.get(facility_id=530012)
        self.assertEqual(iona.held_in_storage_tj, 14474.3)
        self.assertAlmostEqual(iona.net_storage_change_tj, -159.8, places=3)

    def test_flows_for_unknown_facilities_are_reported_not_stored(self):
        report = services.ingest_report('flows', text=(
            'GasDate,FacilityName,FacilityId,FacilityType,Demand,Supply,TransferIn,TransferOut,'
            'HeldInStorage,CushionGasStorage,State,LocationName,LocationId,LastUpdated\n'
            '2026/08/06,Ghost,404404,PIPE,1.0,0.0,0.0,0.0,,,VIC,Adelaide,550016,2026/08/07 11:00:00\n'
        ))
        self.assertEqual(report['stored'], 0)
        self.assertEqual(report['orphaned'], 1)

    def test_linepack_flag_gas_date_drops_the_assessment_time(self):
        """The 15:15 stamp is when AEMO assessed, not part of the day's identity."""
        report = services.ingest_report('linepack_adequacy', text=LCA_CSV)
        self.assertEqual(report['stored'], 2)
        self.assertEqual(
            set(LinepackAdequacy.objects.values_list('gas_date', flat=True)),
            {date(2026, 8, 7), date(2026, 8, 8)},
        )

    def test_forecasts_are_stored_apart_from_actuals(self):
        services.ingest_report('flows', text=FLOWS_CSV)
        services.ingest_report('forecasts', text=FORECASTS_CSV)
        self.assertEqual(FlowForecast.objects.count(), 1)
        self.assertFalse(FlowObservation.objects.filter(gas_date=date(2026, 8, 12)).exists())

    def test_missing_submissions_are_ingested_as_observations(self):
        report = services.ingest_report('missing', text=MISSING_CSV)
        self.assertEqual(report['stored'], 1)
        self.assertEqual(MissingSubmission.objects.first().connection_point_id, -1)


class PictureTests(TestCase):

    def setUp(self):
        services.ingest_reference_report('locations', text=LOCATIONS_CSV)
        services.ingest_reference_report('facilities', text=FACILITIES_CSV)
        services.ingest_report('flows', text=FLOWS_CSV)

    def test_end_use_excludes_pipeline_receipts(self):
        """Adding pipeline demand to plant demand counts the same gas twice."""
        picture = services.gas_day_picture()
        self.assertEqual(picture['gas_date'], date(2026, 8, 6))
        codes = {e['code'] for e in picture['end_use']}
        self.assertIn('BBLARGE', codes)
        self.assertNotIn('PIPE', codes)
        self.assertAlmostEqual(picture['end_use_total_tj'], 0.320, places=3)
        self.assertAlmostEqual(picture['pipeline_receipts_tj'], 507.098, places=3)

    def test_picture_counts_facilities_not_rows(self):
        picture = services.gas_day_picture()
        self.assertEqual(picture['rows'], 4)
        self.assertEqual(picture['reporting_facilities'], 3)

    def test_picture_is_none_before_any_flows(self):
        FlowObservation.objects.all().delete()
        self.assertIsNone(services.gas_day_picture())


class SeriesTests(TestCase):
    """The chart payloads, and the boundaries they must respect."""

    def setUp(self):
        services.ingest_reference_report('locations', text=LOCATIONS_CSV)
        services.ingest_reference_report('facilities', text=FACILITIES_CSV)
        Facility.objects.create(facility_id=544273, name='Australia Pacific LNG',
                                facility_type='LNGEXPORT', operating_state='ACTIVE')
        Facility.objects.create(facility_id=522004, name='Smithfield Energy Facility',
                                facility_type='BBGPG', operating_state='ACTIVE')

    def _flow(self, gas_date, facility_id, demand):
        FlowObservation.objects.create(
            gas_date=gas_date, facility_id=facility_id, location_id=550016,
            demand_tj=demand, supply_tj=0.0, transfer_in_tj=0.0, transfer_out_tj=0.0,
        )

    def test_demand_series_never_starts_before_the_2023_expansion(self):
        """Before 15 Mar 2023 no end-use facility reported at all."""
        self._flow(date(2026, 8, 6), 544273, 3732.0)
        series = services.demand_composition(days=3000, end=date(2026, 8, 6))
        self.assertEqual(series['start'], date(2023, 3, 15))
        self.assertTrue(series['truncated'])

    def test_a_short_window_is_not_marked_truncated(self):
        self._flow(date(2026, 8, 6), 544273, 3732.0)
        series = services.demand_composition(days=30, end=date(2026, 8, 6))
        self.assertFalse(series['truncated'])
        self.assertEqual(series['start'], date(2026, 7, 8))

    def test_demand_series_excludes_pipelines(self):
        self._flow(date(2026, 8, 6), 544273, 3732.0)
        self._flow(date(2026, 8, 6), 522004, 573.0)
        self._flow(date(2026, 8, 6), 530110, 5604.0)   # VTS, a pipeline
        series = services.demand_composition(days=30, end=date(2026, 8, 6))
        codes = {s['code'] for s in series['series']}
        self.assertEqual(codes, {'LNGEXPORT', 'BBGPG'})

    def test_demand_series_is_dense_across_the_window(self):
        """Every series carries one value per date, zero-filled, so the
        stacked bands cannot drift out of alignment."""
        self._flow(date(2026, 8, 5), 544273, 3700.0)
        self._flow(date(2026, 8, 6), 544273, 3732.0)
        self._flow(date(2026, 8, 6), 522004, 573.0)
        series = services.demand_composition(days=30, end=date(2026, 8, 6))
        for entry in series['series']:
            self.assertEqual(len(entry['values']), len(series['dates']))
        gpg = next(s for s in series['series'] if s['code'] == 'BBGPG')
        self.assertEqual(gpg['values'][0], 0.0)

    def _flag(self, gas_date, facility_id, flag):
        LinepackAdequacy.objects.create(gas_date=gas_date, facility_id=facility_id, flag=flag)

    def test_constraint_strip_returns_only_pipelines_ever_flagged(self):
        for offset in range(10):
            day = date(2026, 8, 1) + timedelta(days=offset)
            self._flag(day, 530110, 'AMBER' if offset < 8 else 'GREEN')
            self._flag(day, 540001, 'GREEN')

        strip = services.constraint_history(days=30, end=date(2026, 8, 10))
        self.assertEqual(strip['pipelines_assessed'], 2)
        self.assertEqual(strip['pipelines_flagged'], 1)
        self.assertEqual(strip['rows'][0]['name'], 'VTS')
        self.assertEqual(strip['rows'][0]['constrained_days'], 8)

    def test_a_permanently_flagged_pipeline_reads_as_chronic(self):
        for offset in range(10):
            self._flag(date(2026, 8, 1) + timedelta(days=offset), 530110, 'AMBER')
        strip = services.constraint_history(days=30, end=date(2026, 8, 10))
        self.assertTrue(strip['rows'][0]['chronic'])

    def test_an_occasionally_flagged_pipeline_reads_as_episodic(self):
        for offset in range(10):
            flag = 'AMBER' if offset < 2 else 'GREEN'
            self._flag(date(2026, 8, 1) + timedelta(days=offset), 530110, flag)
        strip = services.constraint_history(days=30, end=date(2026, 8, 10))
        self.assertFalse(strip['rows'][0]['chronic'])

    def test_outlook_stops_where_the_system_wide_assessment_stops(self):
        """One NT pipeline publishes a year of its own outlooks. Listing
        them turned three useful rows into a 325-row table."""
        # Mirrors the real shape: a broad assessment for three gas days,
        # then a single operator publishing far beyond it.
        broad = [Facility.objects.create(facility_id=900000 + n, name=f'Pipe {n}',
                                         facility_type='PIPE', operating_state='ACTIVE')
                 for n in range(10)]
        for offset in range(3):
            day = date(2026, 8, 10) + timedelta(days=offset)
            for index, facility in enumerate(broad):
                self._flag(day, facility.facility_id, 'AMBER' if index == 0 else 'GREEN')
        for offset in range(3, 300):
            self._flag(date(2026, 8, 10) + timedelta(days=offset), 555091, 'GREEN')

        outlook = services.constraint_outlook(today=date(2026, 8, 10))
        self.assertEqual(len(outlook), 3)
        self.assertEqual(outlook[-1]['gas_date'], date(2026, 8, 12))

    def test_trailing_days_default_reproduces_forward_only_behaviour(self):
        """trailing_days=0 must match the pre-existing forward-only
        semantics exactly, since the view's earlier call sites depend on it."""
        for offset in range(3):
            self._flag(date(2026, 8, 10) + timedelta(days=offset), 530110, 'AMBER')
        outlook = services.constraint_outlook(today=date(2026, 8, 10))
        self.assertTrue(all(not day['observed'] for day in outlook))

    def test_trailing_days_adds_observed_history_before_today(self):
        """Recent OBSERVED days are never subject to the forward horizon's
        threshold cutoff — they are real history, not a forecast padded
        out by a single operator."""
        for offset in range(-4, 3):
            self._flag(date(2026, 8, 10) + timedelta(days=offset), 530110, 'AMBER')
        outlook = services.constraint_outlook(today=date(2026, 8, 10), trailing_days=4)
        self.assertEqual(len(outlook), 7)
        self.assertEqual(outlook[0]['gas_date'], date(2026, 8, 6))
        for day in outlook:
            self.assertEqual(day['observed'], day['gas_date'] < date(2026, 8, 10))

    def test_strip_daily_totals_count_flagged_pipelines(self):
        self._flag(date(2026, 8, 1), 530110, 'RED')
        self._flag(date(2026, 8, 1), 540001, 'GREEN')
        strip = services.constraint_history(days=5, end=date(2026, 8, 1))
        self.assertEqual(strip['totals'][-1]['constrained'], 1)
        self.assertEqual(strip['totals'][-1]['assessed'], 2)

    def test_series_are_none_when_there_is_nothing_to_draw(self):
        self.assertIsNone(services.demand_composition())
        self.assertIsNone(services.constraint_history(days=5, end=date(2026, 8, 1)))


class UtilisationTests(TestCase):
    """Capacity is effective-dated, and the denominator has a known limit."""

    def setUp(self):
        services.ingest_reference_report('locations', text=LOCATIONS_CSV)
        services.ingest_reference_report('facilities', text=FACILITIES_CSV)

    def _rating(self, capacity, effective, receipt=1, delivery=2):
        NameplateRating.objects.create(
            facility_id=530110, capacity_type='MDQ', capacity_tj=capacity,
            effective_date=effective, receipt_location_id=receipt, delivery_location_id=delivery,
        )

    def _flow(self, gas_date, supply=0.0, transfer_in=0.0, demand=0.0, transfer_out=0.0):
        FlowObservation.objects.create(
            gas_date=gas_date, facility_id=530110, location_id=550016,
            supply_tj=supply, transfer_in_tj=transfer_in,
            demand_tj=demand, transfer_out_tj=transfer_out,
        )

    def test_capacity_uses_the_rating_in_force_not_the_latest(self):
        """Joining to today's rating rewrites history on every re-rating."""
        self._rating(100.0, date(2024, 1, 1))
        self._rating(500.0, date(2026, 8, 10))

        in_force = services.capacity_in_force([530110], date(2026, 8, 9))
        self.assertEqual(in_force[530110][0], 100.0)
        self.assertEqual(in_force[530110][1], date(2024, 1, 1))

        later = services.capacity_in_force([530110], date(2026, 8, 10))
        self.assertEqual(later[530110][0], 500.0)

    def test_a_facility_with_no_rating_yet_in_force_is_absent_not_zero(self):
        self._rating(500.0, date(2026, 8, 10))
        self.assertEqual(services.capacity_in_force([530110], date(2026, 8, 9)), {})

    def test_capacity_is_the_largest_leg_never_the_sum(self):
        """Bidirectional legs are alternatives; adding them invents capacity."""
        self._rating(400.0, date(2024, 1, 1), receipt=1, delivery=2)
        self._rating(340.0, date(2024, 1, 1), receipt=2, delivery=1)
        self.assertEqual(services.capacity_in_force([530110], date(2026, 1, 1))[530110][0], 400.0)

    def test_throughput_is_receipts_not_deliveries(self):
        self._rating(1000.0, date(2024, 1, 1))
        self._flow(date(2026, 8, 9), supply=161.5, transfer_in=474.5, demand=600.0, transfer_out=20.0)
        row = services.pipeline_utilisation(date(2026, 8, 9))['rated'][0]
        self.assertAlmostEqual(row['received_tj'], 636.0, places=3)
        self.assertAlmostEqual(row['delivered_tj'], 620.0, places=3)

    def test_receipts_above_the_largest_leg_are_flagged_not_counted_as_scarcity(self):
        """A point-to-point rating cannot bound a pipeline receiving at
        several points, so >100% is a limit of the measure."""
        self._rating(512.0, date(2024, 1, 1))
        self._flow(date(2026, 8, 9), supply=161.5, transfer_in=474.5)

        result = services.pipeline_utilisation(date(2026, 8, 9))
        self.assertEqual(len(result['suspect']), 1)
        self.assertTrue(result['rated'][0]['denominator_suspect'])
        self.assertEqual(result['above_90'], 0)
        self.assertEqual(result['meaningful_count'], 0)
        self.assertIsNone(result['busiest'])

    def test_an_ordinary_tight_pipeline_does_count(self):
        self._rating(1000.0, date(2024, 1, 1))
        self._flow(date(2026, 8, 9), transfer_in=940.0)
        result = services.pipeline_utilisation(date(2026, 8, 9))
        self.assertEqual(result['above_90'], 1)
        self.assertFalse(result['rated'][0]['denominator_suspect'])
        self.assertAlmostEqual(result['rated'][0]['utilisation_pct'], 94.0, places=3)


class StorageHistoryTests(TestCase):

    def setUp(self):
        services.ingest_reference_report('locations', text=LOCATIONS_CSV)
        services.ingest_reference_report('facilities', text=FACILITIES_CSV)
        self.iona = Facility.objects.create(facility_id=530012, name='Iona UGS',
                                            facility_type='STOR', operating_state='ACTIVE')
        self.silver = Facility.objects.create(facility_id=540062, name='Silver Springs',
                                              facility_type='STOR', operating_state='ACTIVE')

    def _held(self, gas_date, facility_id, held):
        FlowObservation.objects.create(
            gas_date=gas_date, facility_id=facility_id, location_id=550016,
            demand_tj=0.0, supply_tj=0.0, transfer_in_tj=0.0, transfer_out_tj=0.0,
            held_in_storage_tj=held,
        )

    def test_seasonal_reference_excludes_the_year_being_drawn(self):
        for year in (2023, 2024, 2025, 2026):
            self._held(date(year, 8, 9), 530012, 100.0 * (year - 2022))
        history = services.storage_history(days=2000, end=date(2026, 8, 9))
        # Median of 100, 200, 300 — the 2026 value of 400 must not appear.
        self.assertEqual(history['reference_latest'], 200.0)

    def test_a_facility_absent_today_is_excluded_from_both_lines(self):
        """Comparing a five-facility total to six-facility history invents
        a shortfall that is not there."""
        for year in (2024, 2025):
            self._held(date(year, 8, 9), 530012, 100.0)
            self._held(date(year, 8, 9), 540062, 900.0)
        self._held(date(2026, 8, 9), 530012, 100.0)   # Silver Springs silent

        history = services.storage_history(days=2000, end=date(2026, 8, 9))
        self.assertEqual(history['latest_total'], 100.0)
        self.assertEqual(history['reference_latest'], 100.0)
        self.assertEqual(history['reporting'][-1], 1)
        self.assertEqual(history['absent_latest'], ['Silver Springs'])

    def test_reference_is_none_when_there_is_no_comparable_history(self):
        self._held(date(2026, 8, 9), 530012, 100.0)
        history = services.storage_history(days=30, end=date(2026, 8, 9))
        self.assertIsNone(history['reference_latest'])

    def test_history_is_none_without_storage_rows(self):
        self.assertIsNone(services.storage_history(days=30, end=date(2026, 8, 9)))


class PercentileTests(TestCase):

    def test_percentile_places_a_value_in_its_history(self):
        self.assertEqual(services.percentile_of(5, [1, 2, 3, 4]), 100.0)
        self.assertEqual(services.percentile_of(0, [1, 2, 3, 4]), 0.0)
        self.assertEqual(services.percentile_of(3, [1, 2, 3, 4]), 62.5)

    def test_percentile_is_none_without_history(self):
        self.assertIsNone(services.percentile_of(5, []))
        self.assertIsNone(services.percentile_of(None, [1, 2]))

    def test_seasonal_percentile_ignores_the_same_year(self):
        """A value must never be compared against itself."""
        series = {date(2024, 8, 9): 10.0, date(2025, 8, 9): 20.0, date(2026, 8, 9): 5.0}
        self.assertEqual(services.seasonal_percentile(series, date(2026, 8, 9)), 0.0)

    def test_seasonal_percentile_only_uses_the_same_time_of_year(self):
        """Judging an August level against every day since 2018 would
        mostly measure the seasonal cycle."""
        series = {date(2025, 8, 9): 50.0, date(2025, 2, 9): 900.0, date(2026, 8, 9): 60.0}
        self.assertEqual(services.seasonal_percentile(series, date(2026, 8, 9)), 100.0)


class NetworkTests(TestCase):

    def setUp(self):
        services.ingest_reference_report('locations', text=LOCATIONS_CSV)
        services.ingest_reference_report('facilities', text=FACILITIES_CSV)
        # Wallumbilla (540032) and Adelaide (550016) come from the shared
        # fixture; these two complete the set the layout table places.
        Location.objects.get_or_create(location_id=540030,
                                       defaults={'name': 'Curtis Island', 'state': 'QLD'})
        Location.objects.get_or_create(location_id=520008,
                                       defaults={'name': 'Sydney', 'state': 'NSW'})

    def _flow(self, facility_id, location_id, **kw):
        FlowObservation.objects.create(
            gas_date=date(2026, 8, 9), facility_id=facility_id, location_id=location_id,
            demand_tj=kw.get('demand', 0.0), supply_tj=kw.get('supply', 0.0),
            transfer_in_tj=kw.get('tin', 0.0), transfer_out_tj=kw.get('tout', 0.0),
        )

    def test_an_edge_is_drawn_from_receipt_to_delivery(self):
        self._flow(530110, 540032, tin=1000.0)
        self._flow(530110, 540030, demand=1000.0)
        network = services.flow_network(date(2026, 8, 9))
        self.assertEqual(len(network['edges']), 1)
        edge = network['edges'][0]
        self.assertEqual((edge['source'], edge['target']), (540032, 540030))
        self.assertAlmostEqual(edge['tj'], 1000.0, places=1)

    def test_a_single_receipt_feeding_measured_deliveries_is_not_inferred(self):
        """All the gas came from one place and the deliveries are reported,
        so nothing is being guessed."""
        self._flow(530110, 540032, tin=1000.0)
        self._flow(530110, 540030, demand=600.0)
        self._flow(530110, 550016, demand=400.0)
        network = services.flow_network(date(2026, 8, 9))
        self.assertTrue(all(not e['inferred'] for e in network['edges']))
        self.assertEqual(network['inferred_pipelines'], 0)

    def test_several_receipts_and_several_deliveries_is_inferred(self):
        self._flow(530110, 540032, tin=600.0)
        self._flow(530110, 550016, supply=400.0)
        self._flow(530110, 540030, demand=500.0)
        self._flow(530110, 520008, demand=500.0)
        network = services.flow_network(date(2026, 8, 9))
        self.assertEqual(network['inferred_pipelines'], 1)
        self.assertTrue(all(e['inferred'] for e in network['edges']))

    def test_self_loops_are_dropped(self):
        """Gas received and delivered at the same location is one row, and
        the movement is already accounted for inside that node."""
        self._flow(530110, 540032, tin=100.0, demand=100.0)
        self.assertEqual(services.flow_network(date(2026, 8, 9))['edges'], [])

    def test_nodes_carry_supply_and_end_use_separately(self):
        self._flow(540001, 540032, supply=900.0)       # Moomba, production
        self._flow(555091, 540030, demand=300.0)       # Adelaide Brighton, large user
        network = services.flow_network(date(2026, 8, 9))
        nodes = {n['id']: n for n in network['nodes']}
        self.assertEqual(nodes[540032]['supply_tj'], 900.0)
        self.assertEqual(nodes[540032]['role'], 'supply')
        self.assertEqual(nodes[540030]['demand_tj'], 300.0)
        self.assertEqual(nodes[540030]['role'], 'demand')

    def test_node_value_is_net_of_supply_and_demand_at_that_location(self):
        """A location that has both a production facility and an end-use
        facility reporting is genuinely net, not just "whichever is
        bigger" — Gippsland (20 supply, 15.3 demand) is the real case
        this covers: net 4.7, not a bare 20 that hides the other side."""
        self._flow(540001, 540032, supply=20.0)
        self._flow(555091, 540032, demand=15.3)
        network = services.flow_network(date(2026, 8, 9))
        node = next(n for n in network['nodes'] if n['id'] == 540032)
        self.assertAlmostEqual(node['net_tj'], 4.7, places=1)
        self.assertEqual(node['role'], 'supply')

    def test_the_lng_export_edge_is_flagged_and_scaled_apart(self):
        """The domestic scale must never be set by the export flow."""
        Facility.objects.create(facility_id=700001, name='Curtis Island LNG',
                                facility_type='LNGEXPORT', operating_state='ACTIVE')
        self._flow(530110, 540032, tin=3000.0)             # pipeline receipt
        self._flow(530110, 540030, demand=3000.0)          # pipeline delivery to Curtis Island
        self._flow(700001, 540030, demand=3000.0)          # the LNG plant itself, same location
        network = services.flow_network(date(2026, 8, 9))
        edge = network['edges'][0]
        self.assertTrue(edge['export'])
        self.assertEqual(network['export_peak_tj'], edge['tj'])
        self.assertEqual(network['domestic_peak_tj'], 0.0)

    def test_legend_examples_are_drawn_from_the_real_distribution(self):
        for i, tj in enumerate([10.0, 40.0, 90.0]):
            fac = Facility.objects.create(facility_id=700100 + i, name='Pipe %s' % i,
                                          facility_type='PIPE', operating_state='ACTIVE')
            self._flow(fac.facility_id, 540032, tin=tj)
            self._flow(fac.facility_id, 550016, demand=tj)
        network = services.flow_network(date(2026, 8, 9))
        self.assertTrue(network['legend_flows'])
        self.assertTrue(all(v > 0 for v in network['legend_flows']))
        self.assertEqual(network['legend_flows'], sorted(network['legend_flows']))


class NetOpposingEdgesTests(TestCase):
    """`_net_opposing_edges()` as a pure function, independent of the
    allocation pipeline that would otherwise be needed to fabricate a
    genuine two-facility opposing pair through fixture data."""

    def _edge(self, source, target, tj, inferred=False, pipelines=None):
        return {'source': source, 'target': target, 'tj': tj,
                'pipelines': pipelines or ['X'], 'inferred': inferred}

    def test_the_larger_direction_survives_with_the_net_value(self):
        edges = {
            (1, 2): self._edge(1, 2, 80.0),
            (2, 1): self._edge(2, 1, 50.0),
        }
        netted = services._net_opposing_edges(edges)
        self.assertEqual(len(netted), 1)
        edge = list(netted.values())[0]
        self.assertEqual((edge['source'], edge['target']), (1, 2))
        self.assertAlmostEqual(edge['tj'], 30.0, places=1)
        self.assertAlmostEqual(edge['gross_forward'], 80.0, places=1)
        self.assertAlmostEqual(edge['gross_reverse'], 50.0, places=1)

    def test_a_one_directional_pair_is_untouched(self):
        edges = {(1, 2): self._edge(1, 2, 80.0)}
        netted = services._net_opposing_edges(edges)
        edge = list(netted.values())[0]
        self.assertAlmostEqual(edge['tj'], 80.0, places=1)
        self.assertEqual(edge['gross_reverse'], 0.0)

    def test_inferred_status_and_pipelines_merge_across_both_directions(self):
        edges = {
            (1, 2): self._edge(1, 2, 80.0, inferred=False, pipelines=['Forward Pipe']),
            (2, 1): self._edge(2, 1, 50.0, inferred=True, pipelines=['Reverse Pipe']),
        }
        netted = services._net_opposing_edges(edges)
        edge = list(netted.values())[0]
        self.assertTrue(edge['inferred'])
        self.assertEqual(edge['pipelines'], ['Forward Pipe', 'Reverse Pipe'])


class LocationStateRegionsTests(TestCase):
    """`location_state_regions()` computes the soft background circles
    that replaced a literal continent outline (which read as "a bit
    strange") behind the restored node-link diagram."""

    def setUp(self):
        services.ingest_reference_report('locations', text=LOCATIONS_CSV)
        services.ingest_reference_report('facilities', text=FACILITIES_CSV)
        Location.objects.get_or_create(location_id=540030,
                                       defaults={'name': 'Curtis Island', 'state': 'QLD'})

    def _node(self, location_id, x, y):
        return {'id': location_id, 'label': 'x', 'x': x, 'y': y,
                'supply_tj': 0.0, 'demand_tj': 0.0, 'role': 'transit'}

    def test_one_region_per_state_present_among_the_nodes(self):
        nodes = [self._node(540032, 0.74, 0.35), self._node(550016, 0.46, 0.63)]
        regions = services.location_state_regions(nodes)
        self.assertEqual({r['state'] for r in regions}, {'QLD', 'SA'})

    def test_a_region_centres_on_its_own_nodes(self):
        """Wallumbilla and Curtis Island are both QLD; the region must sit
        between them, not at either one alone."""
        nodes = [self._node(540032, 0.74, 0.35), self._node(540030, 0.89, 0.28)]
        regions = services.location_state_regions(nodes)
        qld = next(r for r in regions if r['state'] == 'QLD')
        self.assertAlmostEqual(qld['cx'], 0.815, places=2)
        self.assertAlmostEqual(qld['cy'], 0.315, places=2)
        self.assertEqual(qld['nodes'], 2)

    def test_a_single_node_state_still_gets_a_visible_region(self):
        """A radius with no floor would draw a region the size of a dot."""
        regions = services.location_state_regions([self._node(550016, 0.46, 0.63)])
        self.assertGreater(regions[0]['r'], 0.05)

    def test_no_nodes_means_no_regions(self):
        self.assertEqual(services.location_state_regions([]), [])


class StateBalanceTests(TestCase):

    def setUp(self):
        services.ingest_reference_report('locations', text=LOCATIONS_CSV)
        services.ingest_reference_report('facilities', text=FACILITIES_CSV)

    def test_end_use_and_pipeline_delivery_are_reported_apart(self):
        """Adding them double counts; Victoria needs the second measure
        because its load arrives through a transmission system."""
        FlowObservation.objects.create(
            gas_date=date(2026, 8, 9), facility_id=530110, location_id=550016,
            state='VIC', demand_tj=600.0, supply_tj=0.0, transfer_in_tj=0.0, transfer_out_tj=0.0)
        FlowObservation.objects.create(
            gas_date=date(2026, 8, 9), facility_id=555091, location_id=550016,
            state='VIC', demand_tj=20.0, supply_tj=0.0, transfer_in_tj=0.0, transfer_out_tj=0.0)

        balance = services.state_balance(date(2026, 8, 9))
        vic = next(r for r in balance['rows'] if r['state'] == 'VIC')
        self.assertEqual(vic['end_use_tj'], 20.0)
        self.assertEqual(vic['delivered_tj'], 600.0)
        self.assertNotIn('net_tj', vic)


class ThesisAndReleaseTests(TestCase):
    """The range-selector nav and the node-link diagram it used to sit
    above were both replaced (state-fixed chart windows; a state grid in
    place of the location diagram), so this class covers what remains:
    the thesis essay, the release bar, and where limits now live."""

    def setUp(self):
        services.ingest_reference_report('locations', text=LOCATIONS_CSV)
        services.ingest_reference_report('facilities', text=FACILITIES_CSV)
        services.ingest_reference_report('nameplate', text=NAMEPLATE_CSV)
        services.ingest_report('flows', text=FLOWS_CSV)

    def test_the_thesis_is_present_collapsed_and_names_the_project(self):
        """Available to anyone who wants it, in the way of nobody who does
        not, and carries the project's name and its central claim."""
        response = self.client.get(reverse('gas_monitor:monitor'))
        self.assertContains(response, 'class="gasmon-thesis"')
        self.assertContains(response, 'FlowTrace')
        self.assertContains(response, 'domestic remainder')
        self.assertNotContains(response, '<details class="gasmon-thesis" open')

    def test_the_thesis_has_no_bullet_lists(self):
        """Rewritten as prose; a table is used instead wherever the page
        needs to show structured data."""
        response = self.client.get(reverse('gas_monitor:monitor'))
        thesis = response.content.decode().split('class="gasmon-thesis__body"')[1]
        thesis = thesis.split('</details>')[0]
        self.assertNotIn('<ul>', thesis)
        self.assertNotIn('<li>', thesis)

    def test_gas_day_convention_is_stated_in_the_release_bar(self):
        """Moved out of the (now much shorter) thesis into the release
        bar, since it is needed to read every date on the page."""
        response = self.client.get(reverse('gas_monitor:monitor'))
        self.assertContains(response, '06:00')

    def test_limits_are_stated_at_their_point_of_use(self):
        """The standalone Data boundary section was removed; each caveat
        now sits in the section it actually governs rather than being
        centralised, so this checks each one where it now lives."""
        response = self.client.get(reverse('gas_monitor:monitor'))
        self.assertNotContains(response, 'gasmon-boundary')
        self.assertContains(response, 'Western Australia')          # network section
        self.assertContains(response, 'capacity in force')          # utilisation section
        self.assertContains(response, 'Allocated estimate')         # network legend

    def test_the_release_bar_states_cadence_and_currency(self):
        response = self.client.get(reverse('gas_monitor:monitor'))
        self.assertContains(response, 'Runs Mondays at 09:00 Australia/Sydney')
        self.assertContains(response, 'Not live data')

    def test_no_range_selector_remains(self):
        """Ranges are now fixed per chart rather than chosen on the page."""
        response = self.client.get(reverse('gas_monitor:monitor'))
        self.assertNotContains(response, 'gasmon-ranges')

    def test_the_network_payload_carries_nodes_and_regions(self):
        """The renderer holds no map of its own: geography arrives as
        state regions computed from the nodes, not a hand-drawn outline."""
        response = self.client.get(reverse('gas_monitor:monitor'))
        network = response.context['network_json']
        self.assertTrue(network['nodes'])
        self.assertIn('regions', network)
        for region in network['regions']:
            self.assertIn('state', region)
            self.assertIn('r', region)


class CoverageTests(TestCase):

    def setUp(self):
        services.ingest_reference_report('locations', text=LOCATIONS_CSV)
        services.ingest_reference_report('facilities', text=FACILITIES_CSV)

    def test_ingesting_flows_records_coverage(self):
        services.ingest_report('flows', text=FLOWS_CSV)
        coverage = {row['source']: row for row in services.coverage_report()}
        self.assertEqual(coverage['flows']['latest_gas_date'], date(2026, 8, 6))
        self.assertEqual(coverage['flows']['earliest_gas_date'], date(2026, 8, 5))
        self.assertTrue(coverage['flows']['loses_data_if_skipped'])

    def test_forward_sources_are_not_at_risk_of_data_loss(self):
        services.ingest_report('linepack_adequacy', text=LCA_CSV)
        coverage = {row['source']: row for row in services.coverage_report()}
        self.assertFalse(coverage['linepack_adequacy']['loses_data_if_skipped'])
        self.assertIsNone(coverage['linepack_adequacy']['days_until_loss'])

    def test_a_forward_source_reads_as_ahead_not_negatively_behind(self):
        services.ingest_report('linepack_adequacy', text=LCA_CSV)
        rows = services.coverage_report(today=date(2026, 8, 6))
        lca = next(r for r in rows if r['source'] == 'linepack_adequacy')
        self.assertIsNone(lca['days_behind'])
        self.assertEqual(lca['days_ahead'], 2)

    def test_margin_shrinks_as_the_data_ages(self):
        services.ingest_report('flows', text=FLOWS_CSV)
        # Ten days after the latest gas day, 21 of the 31-day window remain.
        rows = services.coverage_report(today=date(2026, 8, 16))
        flows = next(r for r in rows if r['source'] == 'flows')
        self.assertEqual(flows['days_behind'], 10)
        self.assertEqual(flows['days_until_loss'], 21)

    def test_a_missed_gas_day_is_detected(self):
        services.ingest_report('flows', text=FLOWS_CSV)
        FlowObservation.objects.filter(gas_date=date(2026, 8, 5)).delete()
        FlowObservation.objects.create(
            gas_date=date(2026, 8, 4), facility_id=530110, location_id=550016,
            demand_tj=1.0, supply_tj=0.0, transfer_in_tj=0.0, transfer_out_tj=0.0,
        )
        self.assertEqual(services.gas_day_gaps(), [date(2026, 8, 5)])

    def test_no_gaps_in_a_contiguous_record(self):
        services.ingest_report('flows', text=FLOWS_CSV)
        self.assertEqual(services.gas_day_gaps(), [])


class ViewTests(TestCase):

    def test_empty_state_says_so_rather_than_showing_zeroes(self):
        response = self.client.get(reverse('gas_monitor:monitor'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No system model loaded yet')

    def test_populated_page_lists_pipelines(self):
        services.ingest_reference_report('locations', text=LOCATIONS_CSV)
        services.ingest_reference_report('facilities', text=FACILITIES_CSV)
        services.ingest_reference_report('nameplate', text=NAMEPLATE_CSV)

        response = self.client.get(reverse('gas_monitor:monitor'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'VTS')
        self.assertContains(response, 'Registered facilities')

    def test_page_names_what_is_not_built_yet(self):
        """Current behaviour must stay distinguishable from future ambition."""
        services.ingest_reference_report('locations', text=LOCATIONS_CSV)
        services.ingest_reference_report('facilities', text=FACILITIES_CSV)
        response = self.client.get(reverse('gas_monitor:monitor'))
        self.assertContains(response, 'Prices are not yet built into FlowTrace')

    def test_reference_tables_are_behind_a_disclosure(self):
        """They are lookup material, not findings, and dominated the page."""
        services.ingest_reference_report('locations', text=LOCATIONS_CSV)
        services.ingest_reference_report('facilities', text=FACILITIES_CSV)
        response = self.client.get(reverse('gas_monitor:monitor'))
        self.assertContains(response, '<details class="gasmon-counts')

    def test_gas_day_content_appears_once_flows_exist(self):
        """The headline snapshot and the coverage disclosure both key off
        the presence of flow data, so they render together."""
        services.ingest_reference_report('locations', text=LOCATIONS_CSV)
        services.ingest_reference_report('facilities', text=FACILITIES_CSV)
        services.ingest_report('flows', text=FLOWS_CSV)
        response = self.client.get(reverse('gas_monitor:monitor'))
        self.assertContains(response, 'System snapshot')
        self.assertContains(response, 'Data currency')
