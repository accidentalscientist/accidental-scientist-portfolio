"""Shared constants for the East Coast Gas System Stress Monitor.

Kept free of Django imports so parsing stays unit-testable without a
database or settings module, matching `nem_price_lab.constants`.
"""

from datetime import date, timedelta, timezone

# ── Gas market time ───────────────────────────────────────────────────
# AEMO's gas timestamps are market time: a FIXED UTC+10 offset that never
# observes daylight saving. This is the same trap the price lab documents
# for electricity, and it bites harder here because the gas day is a
# calendar-like label rather than an instant: shifting it by an hour can
# move a whole day's flows onto the wrong date.
AEST = timezone(timedelta(hours=10), name='AEST')

# The DWGM and the Bulletin Board both start the gas day at 06:00 AEST, so
# the gas day labelled 6 August runs 06:00 on the 6th to 06:00 on the 7th.
# The STTM and the Gas Supply Hub currently use a DIFFERENT start, and an
# AEMC rule change to harmonise them is live. Any calculation that puts a
# GBB flow next to an STTM price is therefore comparing two different
# 24-hour windows until that conversion is written and tested. It is not
# written yet, so nothing in this app overlays the two.
GAS_DAY_START_HOUR = 6

# ── Sources ───────────────────────────────────────────────────────────
# Every Bulletin Board report is an unauthenticated HTTP GET on a public
# directory, which is why this app fetches rather than asking a human to
# download and upload files.
GBB_BASE = 'https://nemweb.com.au/Reports/Current/GBB/'

# The reference ("static system model") reports. These describe the system
# rather than what flowed through it, and are snapshots of current state:
# re-fetching replaces what is stored rather than extending a history.
REFERENCE_REPORTS = {
    'basins': 'GasBBBasins.csv',
    'locations': 'GasBBLocationsList.CSV',
    'facilities': 'GasBBFacilities.CSV',
    'connection_points': 'GasBBNodesAndConnectionPoints.CSV',
    'demand_zones': 'GasBBDemandZonesPipelineConnectionPointMapping.csv',
    'linepack_zones': 'GasBBLinepackZones.CSV',
    'nameplate': 'GasBBNameplateRatingCurrent.csv',
}

# The time-series reports: what actually flowed, what is nominated to flow,
# and where linepack is forecast to be inadequate.
#
# These are ROLLING WINDOWS, which is the single most important operational
# fact about this app. `Last31` holds roughly 31 gas days (30 were present
# on 10 August 2026). Data that falls out of the window is not stale, it is
# GONE from Current/ and recoverable only from nemweb's Archive tree. The
# Price Predictor Lab's AEMO file is cumulative within the month and
# forgives a missed refresh; this does not.
TIME_SERIES_REPORTS = {
    'flows': 'GasBBActualFlowStorageLast31.CSV',
    'forecasts': 'GasBBNominationAndForecastNext7.CSV',
    'linepack_adequacy': 'GasBBLinepackCapacityAdequacyFuture.CSV',
    'missing': 'GasBBMissingActualFlowAndStorage.CSV',
}

# Full-history archives, zipped, for the one-time backfill. Each holds the
# same columns as its rolling counterpart, so the same parser reads both.
# The flow archive held 435,688 rows across 2,871 gas days from
# 29 September 2018 to 8 August 2026 when measured on 10 August 2026.
ARCHIVE_REPORTS = {
    'flows': 'GasBBActualFlowStorage.zip',
    'linepack_adequacy': 'GasBBLinepackCapacityAdequacyFullList.zip',
    # Mandatory, not optional. `GasBBNameplateRatingCurrent.csv` holds only
    # what is in force NOW: on 10 August 2026 every Moomba to Sydney rating
    # carried an effective date of 2026-08-10, so gas day 2026-08-09 had no
    # rating in force at all and utilisation was uncomputable. The archive
    # carries 133,997 rows back to 1 April 2019, which is what makes
    # "the rating in force on that gas day" a real lookup rather than a
    # phrase.
    'nameplate': 'GasBBNameplateRating.zip',
}

# How many gas days each source keeps in Current/, measured rather than
# assumed: on 10 August 2026 the flow file held 30 gas days and the
# missing-submission file held 365. Used by the coverage check to say how
# long a refresh can be skipped before data is lost, so the tolerance is
# derived from the sources rather than asserted in prose.
#
# The flow file is the binding constraint at 31 days. Everything else is
# either far longer or forward-looking, so "when must I refresh" is really
# a question about this one report.
SOURCE_WINDOW_DAYS = {
    'flows': 31,
    'forecasts': 7,           # forward only; nothing is lost by missing one
    'linepack_adequacy': 3,   # forward only
    'missing': 365,           # a full year, not the 31 the name suggests
}

# Sources whose window is BACKWARD-looking. Only these can lose data when a
# refresh is skipped: a forward report simply publishes a new outlook.
BACKWARD_WINDOW_SOURCES = ['flows', 'missing']

# nemweb is public but not free infrastructure. Identify the client and keep
# the request rate low enough that a weekly refresh is invisible.
USER_AGENT = 'accidentalscientist.net gas-monitor (+https://accidentalscientist.net)'
HTTP_TIMEOUT = 120

# ── Units ─────────────────────────────────────────────────────────────
# Bulletin Board quantities are terajoules. Storage holdings are also TJ,
# which is why the dashboard must divide by 1000 to speak in PJ rather than
# assuming the source already did. Iona held 14,474 TJ on 6 August 2026,
# which is 14.5 PJ; reading that figure as PJ overstates it by a thousand.
TJ_PER_PJ = 1000.0

# ── Market structure ──────────────────────────────────────────────────
# Facility types as published in the registry, with the counts observed on
# 7 August 2026 recorded so an unexpected shrink is noticeable.
FACILITY_TYPES = {
    'PIPE': 'Pipeline',
    'PROD': 'Production',
    'BBGPG': 'Gas-powered generation',
    'BBLARGE': 'Large user',
    'STOR': 'Storage',
    'COMPRESSOR': 'Compression',
    'LNGEXPORT': 'LNG export',
    'BDIST': 'Blended distribution',
}

# The types that consume gas as an END USE. Pipelines also report "demand",
# but that is gas received for transport, so summing demand across every
# type double counts: on 6 August 2026 the WGP pipeline and the QCLNG plant
# each reported 1,517.150 TJ, which is one quantity of gas counted twice.
END_USE_TYPES = ['LNGEXPORT', 'BBGPG', 'BBLARGE', 'BDIST']

SUPPLY_TYPES = ['PROD', 'STOR']

# ── The 2023 reporting discontinuity ──────────────────────────────────
# The Bulletin Board expanded on 15 March 2023. Before that date the flow
# record contains ONLY pipelines, production, storage and compression —
# 88 facilities. On that date LNG export, large users and gas-powered
# generation begin reporting, taking it to 141.
#
# This is the single most dangerous fact in the historical record. An
# end-use demand chart drawn across the boundary shows demand rising from
# literally nothing in March 2023, which is a reporting change wearing the
# costume of a market event. Any series involving END_USE_TYPES must start
# here and say why; pipeline, production and storage series are safe back
# to 2018 and should use the full record.
GBB_EXPANSION_DATE = date(2023, 3, 15)

STATES = ['QLD', 'NSW', 'ACT', 'VIC', 'SA', 'TAS', 'NT']


# ── Schematic layout ──────────────────────────────────────────────────
# The Bulletin Board publishes no coordinates, so node positions are hand
# placed once. This is EXPLICITLY NOT geographic: rather than trace real
# coordinates, states are spread apart as separated clusters so membership
# is legible and interstate corridors read as deliberate paths rather than
# a tangle. Values are fractions of the drawing area.
#
# Verified against `Location.state` on 10 August 2026 (25 locations):
# NT 2, QLD 5, SA 3, NSW 5 (the ACT locations report state=NSW in the
# source, so there is no separate ACT cluster), VIC 9, TAS 1. VIC's nine
# is the densest — Victoria was flagged as the cluster most in need of
# breathing room — so it gets the largest internal spread of any state
# while staying tight enough that its region circle does not swallow SA.
#
# Rough topology, north at the top:
#
#         NT
#               QLD
#    SA                  NSW
#               VIC
#               TAS
#
# QLD sits upper-middle so the QLD-to-NSW corridor runs lower-right; SA
# sits left so the SA-to-VIC corridor runs lower-middle; Culcairn (NSW,
# but the physical NSW-VIC interconnect) sits at the VIC/NSW boundary so
# that corridor has a natural waypoint. Moomba, the busiest single hub outward
# fan (Wallumbilla, Sydney, Adelaide, Ballera, Regional ACT), sits with
# open space on every side so those edges do not bundle.
LOCATION_LAYOUT = {
    # NT — isolated top-left, joined to the eastern system via the NGP.
    580001: (0.14, 0.06, 'Darwin'),
    590017: (0.20, 0.14, 'Regional NT'),

    # QLD — upper-middle. Curtis Island sits apart to the east so the LNG
    # export lane has its own visual room, never crossing the domestic
    # QLD-NSW corridor below it.
    590001: (0.38, 0.08, 'Regional QLD'),       # Surat and Bowen production
    540032: (0.48, 0.16, 'Wallumbilla'),        # the northern hub
    540030: (0.68, 0.09, 'Curtis Island'),      # LNG export, held apart
    540078: (0.32, 0.23, 'Ballera'),
    590002: (0.58, 0.24, 'Brisbane'),

    # SA — left side, mid-height. Moomba is the fan-out hub.
    550017: (0.12, 0.40, 'Moomba'),             # the southern hub
    590013: (0.06, 0.51, 'Regional SA'),
    550016: (0.12, 0.60, 'Adelaide'),

    # NSW — right side. Culcairn is the deliberate VIC bridge point.
    590011: (0.80, 0.35, 'Regional NSW'),
    520008: (0.92, 0.43, 'Sydney'),
    590015: (0.78, 0.49, 'Regional ACT'),
    520009: (0.84, 0.55, 'Canberra'),
    590016: (0.72, 0.60, 'Culcairn'),           # the NSW-VIC interconnect

    # VIC — lower-middle, deliberately the tightest cluster of the nine
    # so its region circle stays legible against SA and NSW either side.
    590004: (0.38, 0.72, 'Western VIC'),
    530016: (0.40, 0.80, 'Iona'),               # storage
    590005: (0.44, 0.86, 'Geelong'),
    590006: (0.40, 0.68, 'Ballarat'),
    590012: (0.48, 0.76, 'Regional VIC'),
    590008: (0.50, 0.70, 'Melbourne'),
    590007: (0.55, 0.66, 'Northern VIC'),       # nearest VIC point to Culcairn
    590009: (0.58, 0.75, 'Gippsland'),
    530015: (0.62, 0.82, 'Longford'),           # Bass Strait production

    # TAS — isolated south of Victoria.
    590014: (0.62, 0.95, 'Regional TAS'),
}

# Always labelled at rest, regardless of interaction: curated rather than
# derived purely from net magnitude, because a couple of these (Wallumbilla
# most of all) are major by how much gas passes THROUGH them, not by their
# own net position, which the magnitude alone would miss.
MAJOR_HUBS = {
    540030,  # Curtis Island — LNG export
    590001,  # Regional QLD — the dominant supply node
    540032,  # Wallumbilla — the northern trading hub
    550017,  # Moomba — the southern trading hub, busiest fan-out
    520008,  # Sydney
    590008,  # Melbourne
    530015,  # Longford — Bass Strait production
    530016,  # Iona — the largest storage facility
}

# ── Linepack capacity adequacy ────────────────────────────────────────
# AEMO's own forward assessment of whether a pipeline can meet nominated
# flows. This is the most direct "becoming constrained" signal published
# anywhere in the dataset, and it is forward-looking, which is why it
# matters more than any utilisation percentage computed after the fact.
#
# RED is defined by AEMO but was not present in the window observed on
# 10 August 2026 (51 GREEN, 2 AMBER per gas day). It is listed here so the
# absence of a red flag is a fact about the market rather than a gap in
# this app's vocabulary.
LCA_FLAGS = {
    'GREEN': 'Adequate',
    'AMBER': 'Threatened',
    'RED': 'Inadequate',
}
LCA_CONSTRAINED_FLAGS = ['AMBER', 'RED']

# The Bulletin Board covers the eastern system and the Northern Territory,
# which the Northern Gas Pipeline physically connects to Queensland. NT is
# kept rather than filtered out, because excluding it would draw a boundary
# the data does not draw. Western Australia runs a separate Bulletin Board
# and is genuinely a different system, so it is out of scope.
INCLUDED_STATES = STATES
