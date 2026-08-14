import csv
import json
import math
import statistics
import time
from collections import defaultdict
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand, CommandError


WORLD_BANK_API = 'https://api.worldbank.org/v2'
ATLAS_API = 'https://atlas.hks.harvard.edu/api/graphql'
BIS_API = 'https://stats.bis.org/api/v1/data'
UIS_API = 'https://api.uis.unesco.org/api/public/data/indicators'
SIPRI_API = 'https://atbackend.sipri.org/api/p/trades/import-export-top-csv-str/'
SIPRI_TOP_N = 150
SIPRI_NAME_ALIASES = {
    'russia': 'RUS', 'south korea': 'KOR', 'north korea': 'PRK', 'egypt': 'EGY',
    'slovakia': 'SVK', 'vietnam': 'VNM', 'viet nam': 'VNM', 'czech republic': 'CZE',
    'turkey': 'TUR', 'syria': 'SYR', 'laos': 'LAO', 'iran': 'IRN', 'venezuela': 'VEN',
    'brunei': 'BRN', 'moldova': 'MDA', 'tanzania': 'TZA', 'bolivia': 'BOL',
    'democratic republic of the congo': 'COD', 'republic of the congo': 'COG',
    'united arab emirates': 'ARE', 'ivory coast': 'CIV',
}
START_YEAR = 2015
END_YEAR = 2024
BASELINE_START_YEAR = 2000
ATLAS_YEAR = 2024
MIN_OBSERVATIONS = 5
MIN_LATEST_YEAR = 2020
COHORT_SIZE_V1 = 48
COHORT_SIZE_V2 = 60
MIN_APPROXIMATION_PEERS = 3
COMPATRIOT_POOL_SIZE = 5
SIPRI_CSV_PATH = Path(__file__).resolve().parents[2] / 'data' / 'sipri_arms_exports.csv'

INDICATORS = {
    'gdp_ppp': {
        'id': 'NY.GDP.MKTP.PP.CD', 'label': 'GDP at purchasing power parity',
        'unit': 'current international $', 'aggregation': 'latest', 'transform': 'log10',
        'source': 'World Development Indicators',
    },
    'household_consumption': {
        'id': 'NE.CON.PRVT.PP.CD', 'label': 'Household consumption at purchasing power parity',
        'unit': 'current international $', 'aggregation': 'latest', 'transform': 'log10',
        'source': 'World Development Indicators',
    },
    'gdp_current': {
        'id': 'NY.GDP.MKTP.CD', 'label': 'GDP at market exchange rates',
        'unit': 'current US$', 'aggregation': 'latest', 'transform': 'log10',
        'source': 'World Development Indicators',
    },
    'manufacturing_usd': {
        'id': 'NV.IND.MANF.CD', 'label': 'Manufacturing value added',
        'unit': 'current US$', 'aggregation': 'latest', 'transform': 'log10',
        'source': 'World Development Indicators',
    },
    'industry_usd': {
        'id': 'NV.IND.TOTL.CD', 'label': 'Industry value added',
        'unit': 'current US$', 'aggregation': 'latest', 'transform': 'log10',
        'source': 'World Development Indicators',
    },
    'population': {
        'id': 'SP.POP.TOTL', 'label': 'Population', 'unit': 'people',
        'aggregation': 'latest', 'transform': 'log10', 'source': 'World Development Indicators',
    },
    'reserves_usd': {
        'id': 'FI.RES.TOTL.CD', 'label': 'International reserves', 'unit': 'current US$',
        'aggregation': 'latest', 'transform': 'log10', 'source': 'World Development Indicators',
    },
    'gdp_growth': {
        'id': 'NY.GDP.MKTP.KD.ZG', 'label': 'Real GDP growth', 'unit': '% annual',
        'aggregation': 'average', 'source': 'World Development Indicators',
    },
    'gdp_per_capita_growth': {
        'id': 'NY.GDP.PCAP.KD.ZG', 'label': 'Real GDP per capita growth', 'unit': '% annual',
        'aggregation': 'average', 'source': 'World Development Indicators',
    },
    'recent_growth': {
        'label': 'Recent real GDP growth', 'unit': '% annual', 'aggregation': 'average',
        'source': 'Derived from World Development Indicators',
    },
    'growth_volatility': {
        'label': 'Growth volatility', 'unit': 'percentage points', 'aggregation': 'average',
        'direction': -1, 'source': 'Derived from World Development Indicators',
    },
    'investment': {
        'id': 'NE.GDI.TOTL.ZS', 'label': 'Gross capital formation', 'unit': '% of GDP',
        'aggregation': 'average', 'source': 'World Development Indicators',
    },
    'gross_savings': {
        'id': 'NY.GNS.ICTR.ZS', 'label': 'Gross domestic savings', 'unit': '% of GDP',
        'aggregation': 'average', 'source': 'World Development Indicators',
    },
    'fdi_inflows': {
        'id': 'BX.KLT.DINV.WD.GD.ZS', 'label': 'Foreign direct investment inflows',
        'unit': '% of GDP', 'aggregation': 'average', 'source': 'World Development Indicators',
    },
    'working_age': {
        'id': 'SP.POP.1564.TO.ZS', 'label': 'Working-age population', 'unit': '% of population',
        'aggregation': 'latest', 'source': 'World Development Indicators',
    },
    'population_growth': {
        'id': 'SP.POP.GROW', 'label': 'Population growth', 'unit': '% annual',
        'aggregation': 'average', 'source': 'World Development Indicators',
    },
    'youth_share': {
        'id': 'SP.POP.0014.TO.ZS', 'label': 'Population aged 0-14', 'unit': '% of population',
        'aggregation': 'latest', 'source': 'World Development Indicators',
    },
    'working_age_population': {
        'label': 'Working-age population', 'unit': 'people', 'aggregation': 'latest',
        'transform': 'log10', 'source': 'Derived from World Development Indicators',
    },
    'urban_population': {
        'id': 'SP.URB.TOTL', 'label': 'Urban population', 'unit': 'people',
        'aggregation': 'latest', 'transform': 'log10', 'source': 'World Development Indicators',
    },
    'government_effectiveness': {
        'id': 'GOV_WGI_GE.EST', 'label': 'Government effectiveness', 'unit': 'estimate',
        'aggregation': 'average', 'source': 'Worldwide Governance Indicators',
    },
    'regulatory_quality': {
        'id': 'GOV_WGI_RQ.EST', 'label': 'Regulatory quality', 'unit': 'estimate',
        'aggregation': 'average', 'source': 'Worldwide Governance Indicators',
    },
    'inflation': {
        'id': 'FP.CPI.TOTL.ZG', 'label': 'Consumer-price inflation', 'unit': '% annual',
        'aggregation': 'average', 'direction': -1, 'source': 'World Development Indicators',
    },
    'current_account': {
        'id': 'BN.CAB.XOKA.GD.ZS', 'label': 'Current-account balance', 'unit': '% of GDP',
        'aggregation': 'average', 'source': 'World Development Indicators',
    },
    'manufacturing_share': {
        'id': 'NV.IND.MANF.ZS', 'label': 'Manufacturing share', 'unit': '% of GDP',
        'aggregation': 'average', 'source': 'World Development Indicators',
    },
    'broadband': {
        'id': 'IT.NET.BBND.P2', 'label': 'Fixed broadband subscriptions',
        'unit': 'per 100 people', 'aggregation': 'latest', 'source': 'World Development Indicators',
    },
    'resource_rents': {
        'id': 'NY.GDP.TOTL.RT.ZS', 'label': 'Natural-resource rents', 'unit': '% of GDP',
        'aggregation': 'average', 'source': 'World Development Indicators',
    },
    'atlas_exports': {
        'label': 'Exports', 'unit': 'current US$', 'aggregation': 'latest',
        'transform': 'log10', 'source': 'Harvard Growth Lab Atlas',
    },
    'atlas_imports': {
        'label': 'Imports', 'unit': 'current US$', 'aggregation': 'latest',
        'transform': 'log10', 'source': 'Harvard Growth Lab Atlas',
    },
    'trade_diversity': {
        'label': 'Effective trade partners', 'unit': 'partner-equivalents',
        'aggregation': 'latest', 'transform': 'log10', 'source': 'Harvard Growth Lab Atlas',
    },
    'eci': {
        'label': 'Economic Complexity Index', 'unit': 'index', 'aggregation': 'latest',
        'source': 'Harvard Growth Lab Atlas',
    },
    'reserve_import_cover': {
        'label': 'Reserve import coverage', 'unit': 'years of imports', 'aggregation': 'latest',
        'source': 'Derived from World Bank and Harvard Growth Lab Atlas',
    },
    'product_diversity': {
        'label': 'Effective export products', 'unit': 'product-equivalents',
        'aggregation': 'latest', 'transform': 'log10', 'source': 'Harvard Growth Lab Atlas',
    },
    'resource_exports': {
        'label': 'Natural-resource exports', 'unit': 'current US$',
        'aggregation': 'latest', 'transform': 'log1p', 'source': 'Harvard Growth Lab Atlas',
    },
    'resource_product_diversity': {
        'label': 'Effective resource export products', 'unit': 'product-equivalents',
        'aggregation': 'latest', 'transform': 'log1p', 'source': 'Harvard Growth Lab Atlas',
    },

    # --- Giga v2 additions below ---
    'labor_force': {
        'id': 'SL.TLF.TOTL.IN', 'label': 'Labor force, total', 'unit': 'people',
        'aggregation': 'latest', 'transform': 'log10', 'source': 'World Development Indicators',
    },
    'tertiary_enrollment': {
        'id': 'SE.TER.ENRR', 'label': 'School enrollment, tertiary', 'unit': '% gross',
        'aggregation': 'average', 'source': 'World Development Indicators', 'approximable': True,
    },
    'elec_consumption_pc': {
        'id': 'EG.USE.ELEC.KH.PC', 'label': 'Electric power consumption per capita',
        'unit': 'kWh per capita', 'aggregation': 'latest', 'source': 'World Development Indicators',
    },
    'elec_access': {
        'id': 'EG.ELC.ACCS.ZS', 'label': 'Access to electricity', 'unit': '% of population',
        'aggregation': 'latest', 'source': 'World Development Indicators',
    },
    'energy_use_pcap': {
        'id': 'EG.USE.PCAP.KG.OE', 'label': 'Energy use per capita',
        'unit': 'kg of oil equivalent per capita', 'aggregation': 'latest',
        'source': 'World Development Indicators',
    },
    'lpi_overall': {
        'id': 'LP.LPI.OVRL.XQ', 'label': 'Logistics Performance Index: overall',
        'unit': 'index (1-5)', 'aggregation': 'latest', 'source': 'World Development Indicators',
        'ignore_recency': True,
    },
    'lpi_infrastructure': {
        'id': 'LP.LPI.INFR.XQ', 'label': 'Logistics Performance Index: infrastructure',
        'unit': 'index (1-5)', 'aggregation': 'latest', 'source': 'World Development Indicators',
        'ignore_recency': True,
    },
    'lpi_intl_shipments': {
        'id': 'LP.LPI.ITRN.XQ', 'label': 'Logistics Performance Index: international shipments',
        'unit': 'index (1-5)', 'aggregation': 'latest', 'source': 'World Development Indicators',
        'ignore_recency': True,
    },
    'credit_private_gdp': {
        'id': 'FS.AST.PRVT.GD.ZS', 'label': 'Domestic credit to private sector',
        'unit': '% of GDP', 'aggregation': 'average', 'source': 'World Development Indicators',
        'bis_supplement': True,
    },
    'market_cap_gdp': {
        'id': 'CM.MKT.LCAP.GD.ZS', 'label': 'Market capitalization of listed domestic companies',
        'unit': '% of GDP', 'aggregation': 'average', 'source': 'World Development Indicators',
        'approximable': True,
    },
    'stocks_traded_gdp': {
        'id': 'CM.MKT.TRAD.GD.ZS', 'label': 'Stocks traded, total value',
        'unit': '% of GDP', 'aggregation': 'average', 'source': 'World Development Indicators',
        'approximable': True,
    },
    'fdi_outflows_gdp': {
        'id': 'BM.KLT.DINV.WD.GD.ZS', 'label': 'Foreign direct investment, net outflows',
        'unit': '% of GDP', 'aggregation': 'average', 'source': 'World Development Indicators',
    },
    'fdi_outflows_usd': {
        'id': 'BM.KLT.DINV.CD.WD', 'label': 'Foreign direct investment, net outflows',
        'unit': 'current US$', 'aggregation': 'average', 'source': 'World Development Indicators',
    },
    'primary_income_receipts': {
        'id': 'BX.GSR.FCTY.CD', 'label': 'Primary income receipts from abroad',
        'unit': 'current US$', 'aggregation': 'average', 'transform': 'log10',
        'source': 'World Development Indicators',
    },
    'hightech_exports': {
        'id': 'TX.VAL.TECH.MF.ZS', 'label': 'High-technology exports',
        'unit': '% of manufactured exports', 'aggregation': 'latest',
        'source': 'World Development Indicators', 'approximable': True,
    },
    'patent_apps_resident': {
        'id': 'IP.PAT.RESD', 'label': 'Patent applications, residents', 'unit': 'applications',
        'aggregation': 'latest', 'transform': 'log1p', 'source': 'World Development Indicators',
    },
    'ip_royalty_receipts': {
        'id': 'BX.GSR.ROYL.CD', 'label': 'Charges for the use of intellectual property, receipts',
        'unit': 'current US$', 'aggregation': 'latest', 'transform': 'log1p',
        'source': 'World Development Indicators', 'approximable': True,
    },
    'wgi_rule_of_law': {
        'id': 'GOV_WGI_RL.EST', 'label': 'Rule of law', 'unit': 'estimate',
        'aggregation': 'average', 'source': 'Worldwide Governance Indicators',
    },
    'wgi_control_corruption': {
        'id': 'GOV_WGI_CC.EST', 'label': 'Control of corruption', 'unit': 'estimate',
        'aggregation': 'average', 'source': 'Worldwide Governance Indicators',
    },
    'wgi_political_stability': {
        'id': 'GOV_WGI_PV.EST', 'label': 'Political stability and absence of violence',
        'unit': 'estimate', 'aggregation': 'average', 'source': 'Worldwide Governance Indicators',
    },
    'rd_expenditure_gdp': {
        'id': 'GB.XPD.RSDV.GD.ZS', 'label': 'Research and development expenditure',
        'unit': '% of GDP', 'aggregation': 'average', 'source': 'World Development Indicators',
        'uis_supplement': 'EXPGDP.TOT', 'approximable': True,
    },
    'researchers_per_million': {
        'id': 'SP.POP.SCIE.RD.P6', 'label': 'Researchers in R&D', 'unit': 'per million people',
        'aggregation': 'latest', 'source': 'World Development Indicators', 'approximable': True,
    },
    'journal_articles': {
        'id': 'IP.JRN.ARTC.SC', 'label': 'Scientific and technical journal articles',
        'unit': 'articles', 'aggregation': 'latest', 'transform': 'log1p',
        'source': 'World Development Indicators',
    },
    'renewable_energy_share': {
        'id': 'EG.FEC.RNEW.ZS', 'label': 'Renewable energy consumption',
        'unit': '% of total final energy consumption', 'aggregation': 'average',
        'source': 'World Development Indicators',
    },
    'renew_electricity_output': {
        'id': 'EG.ELC.RNEW.ZS', 'label': 'Renewable electricity output',
        'unit': '% of total electricity output', 'aggregation': 'average',
        'source': 'World Development Indicators',
    },
    'energy_intensity': {
        'id': 'EG.EGY.PRIM.PP.KD', 'label': 'Energy intensity of GDP',
        'unit': 'MJ per $2017 PPP GDP', 'aggregation': 'average', 'direction': -1,
        'source': 'World Development Indicators',
    },
    'military_expenditure_gdp': {
        'id': 'MS.MIL.XPND.GD.ZS', 'label': 'Military expenditure', 'unit': '% of GDP',
        'aggregation': 'average', 'source': 'World Development Indicators',
    },
    'armed_forces_personnel': {
        'id': 'MS.MIL.TOTL.P1', 'label': 'Armed forces personnel, total', 'unit': 'people',
        'aggregation': 'latest', 'transform': 'log10', 'source': 'World Development Indicators',
    },
    'arms_export_tiv': {
        'label': 'Arms exports (trend-indicator value)', 'unit': 'SIPRI TIV, millions',
        'aggregation': 'latest', 'source': 'SIPRI Arms Transfers Database',
    },
}

APPROXIMATION_ELIGIBLE = sorted(key for key, config in INDICATORS.items() if config.get('approximable'))

PILLARS_V1 = {
    'domestic_market': {
        'label': 'Domestic market', 'description': 'Economic scale, household purchasing power and market-rate weight.',
        'inputs': ['gdp_ppp', 'household_consumption', 'gdp_current'],
    },
    'productive_base': {
        'label': 'Productive base', 'description': 'The scale and intensity of industry already in place.',
        'inputs': ['manufacturing_usd', 'industry_usd', 'manufacturing_share'],
    },
    'trade_power': {
        'label': 'Trade power', 'description': 'Export reach, import pull and breadth across trade partners.',
        'inputs': ['atlas_exports', 'atlas_imports', 'trade_diversity'],
    },
    'financial_buffer': {
        'label': 'Financial buffer', 'description': 'External liquidity, import cover and the observed current-account position.',
        'inputs': ['reserves_usd', 'reserve_import_cover', 'current_account'],
    },
    'population_base': {
        'label': 'Population base', 'description': 'Total, working-age and urban human scale available to mobilise.',
        'inputs': ['population', 'working_age_population', 'urban_population'],
    },
    'momentum': {
        'label': 'Growth momentum', 'description': 'Decade growth, recent growth and per-person growth already observed.',
        'inputs': ['gdp_growth', 'recent_growth', 'gdp_per_capita_growth'], 'bridge_group': 'assets',
    },
    'reinvestment': {
        'label': 'Reinvestment', 'description': 'Investment, domestic savings and foreign capital formation.',
        'inputs': ['investment', 'gross_savings', 'fdi_inflows'], 'bridge_group': 'assets',
    },
    'demographic_runway': {
        'label': 'Demographic runway', 'description': 'Working-age capacity, youth pipeline and population momentum.',
        'inputs': ['working_age', 'youth_share', 'population_growth'], 'bridge_group': 'assets',
    },
    'conversion_capacity': {
        'label': 'Conversion capacity', 'description': 'Institutions and digital infrastructure that turn assets into output.',
        'inputs': ['government_effectiveness', 'regulatory_quality', 'broadband'], 'bridge_group': 'conversion',
    },
    'productive_depth': {
        'label': 'Productive depth', 'description': 'Manufacturing intensity, export complexity and product diversity.',
        'inputs': ['manufacturing_share', 'eci', 'product_diversity'], 'bridge_group': 'conversion',
    },
    'macro_resilience': {
        'label': 'Macro resilience', 'description': 'Price stability, external balance and steadiness through the cycle.',
        'inputs': ['inflation', 'current_account', 'growth_volatility'], 'bridge_group': 'conversion',
    },
    'resource_optionality': {
        'label': 'Resource optionality',
        'description': 'Current rents, export scale and diversity across extractive product groups.',
        'inputs': ['resource_rents', 'resource_exports', 'resource_product_diversity'], 'bridge_group': 'assets',
    },
}

MODELS_V1 = {
    'power': {
        'label': 'Global Power Rankings', 'short_label': 'Power Now',
        'question': 'How much observable economic weight can each country mobilise now?',
        'components': ['domestic_market', 'productive_base', 'trade_power', 'financial_buffer', 'population_base'],
        'method': 'Five observable pillars are standardised within the fixed 48-economy cohort and equally weighted by default.',
    },
    'potential': {
        'label': 'Global Power Potential Rankings', 'short_label': 'Power Potential',
        'question': 'Which present conditions could expand or erode economic power?',
        'components': ['momentum', 'reinvestment', 'demographic_runway', 'conversion_capacity', 'productive_depth', 'macro_resilience', 'resource_optionality'],
        'method': 'Observed 2015–2024 conditions and latest structural measures are standardised within the same cohort; no projection enters the score.',
    },
}

PILLARS_V2 = {
    **PILLARS_V1,
    'population_base': {
        'label': 'Population base',
        'description': 'Total human scale, active labour mobilisation and skill depth available to mobilise.',
        'inputs': ['population', 'labor_force', 'tertiary_enrollment'],
    },
    'energy_base': {
        'label': 'Energy base', 'description': 'Electricity consumption, access and total energy throughput already in use.',
        'inputs': ['elec_consumption_pc', 'elec_access', 'energy_use_pcap'],
    },
    'logistics_reach': {
        'label': 'Logistics reach', 'description': 'Physical capacity to move goods: overall, infrastructure and shipment performance.',
        'inputs': ['lpi_overall', 'lpi_infrastructure', 'lpi_intl_shipments'],
    },
    'financial_depth': {
        'label': 'Capital markets', 'description': 'Domestic bank credit, equity-market size and equity-market liquidity — distinct from Financial buffer, which measures external liquidity.',
        'inputs': ['credit_private_gdp', 'market_cap_gdp', 'stocks_traded_gdp'],
    },
    'global_leverage': {
        'label': 'Global leverage',
        'description': 'Capital and income the economy holds and earns beyond its own borders.',
        'inputs': ['fdi_outflows_gdp', 'fdi_outflows_usd', 'primary_income_receipts'],
    },
    'technology_innovation': {
        'label': 'Technology & innovation',
        'description': 'Current technological output: high-tech exports, patents filed and IP income earned.',
        'inputs': ['hightech_exports', 'patent_apps_resident', 'ip_royalty_receipts'],
    },
    'institutional_depth': {
        'label': 'Institutional depth',
        'description': 'Rule of law, control of corruption and political stability beyond administrative effectiveness.',
        'inputs': ['wgi_rule_of_law', 'wgi_control_corruption', 'wgi_political_stability'],
        'bridge_group': 'conversion',
    },
    'innovation_investment': {
        'label': 'Innovation investment',
        'description': 'R&D spending, researcher density and scientific output being built for tomorrow.',
        'inputs': ['rd_expenditure_gdp', 'researchers_per_million', 'journal_articles'],
        'bridge_group': 'assets',
    },
    'energy_transition': {
        'label': 'Energy transition',
        'description': "Renewable share of energy and electricity, and the trend in the economy's energy intensity.",
        'inputs': ['renewable_energy_share', 'renew_electricity_output', 'energy_intensity'],
        'bridge_group': 'conversion',
    },
}

MODELS_V2 = {
    'power': {
        'label': 'Global Power Rankings', 'short_label': 'Power Now',
        'question': 'How much observable economic weight can each country mobilise now?',
        'components': [
            'domestic_market', 'productive_base', 'trade_power', 'financial_buffer', 'population_base',
            'energy_base', 'logistics_reach', 'financial_depth', 'global_leverage', 'technology_innovation',
        ],
        'method': 'Ten observable pillars are standardised within the fixed 48-economy cohort and equally weighted by default.',
    },
    'potential': {
        'label': 'Global Power Potential Rankings', 'short_label': 'Power Potential',
        'question': 'Which present conditions could expand or erode economic power?',
        'components': [
            'momentum', 'reinvestment', 'demographic_runway', 'conversion_capacity', 'productive_depth',
            'macro_resilience', 'resource_optionality', 'institutional_depth', 'innovation_investment', 'energy_transition',
        ],
        'method': 'Observed 2015–2024 conditions and latest structural measures are standardised within the same cohort; no projection enters the score.',
    },
}


class Command(BaseCommand):
    help = 'Build World Ledger Giga Dataset version 1.0 and version 2.0.'

    def handle(self, *args, **options):
        try:
            countries = self._country_metadata()
            self._valid_iso3s = set(countries)
            observations, updated_dates = self._world_bank_observations(countries)
            atlas = self._atlas_data()
        except (OSError, ValueError, KeyError, TypeError, HTTPError) as exc:
            raise CommandError(f'Data download failed: {exc}') from exc

        prepared = self._prepare_world_bank(countries, observations)
        self._add_derived_wdi_values(prepared, observations)
        self._add_atlas_values(prepared, atlas)
        self._bis_credit_data(countries, prepared)
        self._uis_supplement_data(countries, prepared)
        for note in self._approximate_missing_values(prepared, countries, observations, APPROXIMATION_ELIGIBLE):
            self.stdout.write(self.style.WARNING(note))

        military, arms_vintage = self._military_data(countries, observations)
        data_updated = max(date for date in updated_dates if date)
        base_sources = [
            {'name': 'World Development Indicators', 'url': 'https://databank.worldbank.org/source/world-development-indicators', 'data_as_of': data_updated},
            {'name': 'Worldwide Governance Indicators', 'url': 'https://www.worldbank.org/en/publication/worldwide-governance-indicators', 'data_as_of': data_updated},
            {'name': 'Harvard Growth Lab Atlas of Economic Complexity', 'url': 'https://atlas.hks.harvard.edu/data-downloads/', 'data_as_of': str(ATLAS_YEAR)},
        ]
        sipri_source = {
            'name': 'SIPRI Arms Transfers Database', 'url': 'https://armstransfers.sipri.org/',
            'data_as_of': arms_vintage or 'Not yet loaded — see world_lens/data/sipri_arms_exports.csv',
        }

        v1_payload = self._build_dataset(
            'Giga Dataset version 1.0', COHORT_SIZE_V1, MODELS_V1, PILLARS_V1, countries, prepared, atlas,
            data_updated, base_sources, military=None,
        )
        v2_payload = self._build_dataset(
            'Giga Dataset version 2.0', COHORT_SIZE_V2, MODELS_V2, PILLARS_V2, countries, prepared, atlas,
            data_updated, base_sources + [sipri_source], military=military,
        )

        base_dir = Path(__file__).resolve().parents[2] / 'data'
        base_dir.mkdir(parents=True, exist_ok=True)
        (base_dir / 'world_lens.json').write_text(json.dumps(v1_payload, indent=2, ensure_ascii=False), encoding='utf-8')
        (base_dir / 'world_lens_v2.json').write_text(json.dumps(v2_payload, indent=2, ensure_ascii=False), encoding='utf-8')

        self.stdout.write(self.style.SUCCESS(
            f'Wrote v1 ({len(v1_payload["countries"])} economies) and v2 ({len(v2_payload["countries"])} economies).'
        ))
        self.stdout.write('v1 cohort: ' + ', '.join(c['iso3'] for c in v1_payload['countries']))
        self.stdout.write('v2 cohort: ' + ', '.join(c['iso3'] for c in v2_payload['countries']))

    def _build_dataset(self, dataset_label, cohort_size, models, pillars, countries, prepared, atlas, data_updated, sources, military):
        all_inputs = sorted({key for pillar in pillars.values() for key in pillar['inputs']})
        complete = [
            iso3 for iso3 in countries
            if all(key in prepared[iso3] and self._valid(prepared[iso3][key], INDICATORS[key]) for key in all_inputs)
        ]
        if len(complete) < cohort_size:
            raise CommandError(f'[{dataset_label}] Only {len(complete)} economies have complete coverage; {cohort_size} required.')

        provisional = self._score_model(models['power'], pillars, prepared, complete)
        cohort = sorted(complete, key=lambda code: provisional[code]['score'], reverse=True)[:cohort_size]
        if 'CHN' not in cohort or 'IND' not in cohort:
            raise CommandError(f'[{dataset_label}] The materiality rule unexpectedly excluded China or India.')

        model_results = {key: self._score_model(model, pillars, prepared, cohort) for key, model in models.items()}
        atlas_by_id = atlas['locations_by_id']
        output_countries = []
        for iso3 in sorted(cohort, key=lambda code: countries[code]['name']):
            entry = {
                'iso3': iso3, 'name': countries[iso3]['name'], 'region': countries[iso3]['region'],
                'models': {key: model_results[key][iso3] for key in models},
                'trade_links': self._trade_links(iso3, atlas, atlas_by_id),
            }
            if military is not None:
                entry['military'] = military.get(iso3, {})
            output_countries.append(entry)

        return {
            'meta': {
                'product': 'World Ledger', 'dataset': dataset_label,
                'data_updated': data_updated, 'atlas_year': ATLAS_YEAR, 'cohort_count': cohort_size,
                'score_start': START_YEAR, 'score_end': END_YEAR,
                'minimum_observations': MIN_OBSERVATIONS, 'minimum_latest_year': MIN_LATEST_YEAR,
                'inclusion_rule': (
                    'Complete coverage on every scored input (Compatriot Estimation Method values '
                    f'count as coverage where explicitly flagged), then the top {cohort_size} economies '
                    'under equal-weight Power Now.'
                ),
                'models': models, 'pillars': pillars, 'indicators': INDICATORS,
                'sources': sources,
            },
            'countries': output_countries,
        }

    def _prepare_world_bank(self, countries, observations):
        prepared = defaultdict(dict)
        for iso3 in countries:
            for key, config in INDICATORS.items():
                if 'id' not in config:
                    continue
                series = [item for item in observations[iso3].get(key, []) if item['year'] >= START_YEAR]
                if not series:
                    continue
                if config['aggregation'] == 'average':
                    if len(series) < MIN_OBSERVATIONS:
                        continue
                    prepared[iso3][key] = {
                        'raw': statistics.fmean(item['value'] for item in series),
                        'observations': len(series), 'start_year': min(item['year'] for item in series),
                        'end_year': max(item['year'] for item in series),
                    }
                else:
                    latest = max(series, key=lambda item: item['year'])
                    prepared[iso3][key] = {'raw': latest['value'], 'observations': 1, 'year': latest['year']}
        return prepared

    def _add_derived_wdi_values(self, prepared, observations):
        for iso3, values in prepared.items():
            growth = sorted(observations[iso3].get('gdp_growth', []), key=lambda item: item['year'])
            if len(growth) >= MIN_OBSERVATIONS:
                recent = growth[-3:]
                values['recent_growth'] = {
                    'raw': statistics.fmean(item['value'] for item in recent),
                    'observations': len(recent), 'start_year': recent[0]['year'], 'end_year': recent[-1]['year'],
                }
                values['growth_volatility'] = {
                    'raw': statistics.pstdev(item['value'] for item in growth),
                    'observations': len(growth), 'start_year': growth[0]['year'], 'end_year': growth[-1]['year'],
                }
            if 'population' in values and 'working_age' in values:
                population = values['population']
                working_age = values['working_age']
                values['working_age_population'] = {
                    'raw': population['raw'] * working_age['raw'] / 100,
                    'observations': 1, 'year': min(population['year'], working_age['year']),
                }

    def _add_atlas_values(self, prepared, atlas):
        for iso3, row in atlas['country_year'].items():
            if (
                iso3 not in prepared or row.get('eci') is None
                or not row.get('exportValue') or not row.get('importValue')
            ):
                continue
            exports = [
                edge for edge in atlas['bilateral'].get(iso3, [])
                if edge['value'] > 0
                and atlas['locations_by_id'].get(edge['partner_id'], {}).get('iso3Code') in self._valid_iso3s
            ]
            total = sum(edge['value'] for edge in exports)
            shares = [edge['value'] / total for edge in exports] if total else []
            effective_partners = 1 / sum(share * share for share in shares) if shares else 0
            products = [value for value in atlas['products'].get(iso3, {}).values() if value > 0]
            product_total = sum(products)
            product_shares = [value / product_total for value in products] if product_total else []
            effective_products = 1 / sum(share * share for share in product_shares) if product_shares else 0
            resource_products = [
                value for product_id, value in atlas['products'].get(iso3, {}).items()
                if product_id in atlas['natural_resource_products'] and value > 0
            ]
            resource_total = sum(resource_products)
            resource_shares = [value / resource_total for value in resource_products] if resource_total else []
            effective_resources = 1 / sum(share * share for share in resource_shares) if resource_shares else 0
            prepared[iso3]['atlas_exports'] = {'raw': row['exportValue'], 'observations': 1, 'year': ATLAS_YEAR}
            prepared[iso3]['atlas_imports'] = {'raw': row['importValue'], 'observations': 1, 'year': ATLAS_YEAR}
            prepared[iso3]['eci'] = {'raw': row['eci'], 'observations': 1, 'year': ATLAS_YEAR}
            prepared[iso3]['trade_diversity'] = {'raw': effective_partners, 'observations': 1, 'year': ATLAS_YEAR}
            prepared[iso3]['product_diversity'] = {'raw': effective_products, 'observations': 1, 'year': ATLAS_YEAR}
            prepared[iso3]['resource_exports'] = {'raw': resource_total, 'observations': 1, 'year': ATLAS_YEAR}
            prepared[iso3]['resource_product_diversity'] = {
                'raw': effective_resources, 'observations': 1, 'year': ATLAS_YEAR,
            }
            if 'reserves_usd' in prepared[iso3]:
                prepared[iso3]['reserve_import_cover'] = {
                    'raw': prepared[iso3]['reserves_usd']['raw'] / row['importValue'],
                    'observations': 1,
                    'year': min(prepared[iso3]['reserves_usd']['year'], ATLAS_YEAR),
                }

    def _bis_credit_data(self, countries, prepared):
        for key, config in INDICATORS.items():
            if not config.get('bis_supplement'):
                continue
            filled = 0
            for iso3, meta in countries.items():
                existing = prepared.get(iso3, {}).get(key)
                if existing is not None and self._valid(existing, config):
                    continue
                iso2 = meta.get('iso2')
                if not iso2:
                    continue
                try:
                    url = f'{BIS_API}/WS_TC/Q.{iso2}.P.A.M.770.A?startPeriod={START_YEAR}&format=csv'
                    request = Request(url, headers={'User-Agent': 'World-Ledger/1.0'})
                    with urlopen(request, timeout=60) as response:
                        rows = response.read().decode('utf-8').strip().split('\n')
                except (HTTPError, TimeoutError, OSError, UnicodeDecodeError):
                    continue
                if len(rows) < 2:
                    continue
                header = rows[0].split(',')
                try:
                    period_idx, value_idx = header.index('TIME_PERIOD'), header.index('OBS_VALUE')
                except ValueError:
                    continue
                latest_year, latest_value = None, None
                for line in rows[1:]:
                    cells = line.split(',')
                    if len(cells) <= max(period_idx, value_idx):
                        continue
                    period, raw_value = cells[period_idx], cells[value_idx]
                    year = period.split('-')[0]
                    try:
                        year_int, value_float = int(year), float(raw_value)
                    except ValueError:
                        continue
                    if latest_year is None or year_int >= latest_year:
                        latest_year, latest_value = year_int, value_float
                if latest_value is not None:
                    prepared.setdefault(iso3, {})[key] = {
                        'raw': latest_value, 'observations': 1, 'year': latest_year,
                    }
                    filled += 1
            if filled:
                self.stdout.write(f'BIS supplement filled {key} for {filled} economies missing it in WDI.')

    def _uis_supplement_data(self, countries, prepared):
        for key, config in INDICATORS.items():
            uis_code = config.get('uis_supplement')
            if not uis_code:
                continue
            try:
                url = f'{UIS_API}?indicator={uis_code}&start={BASELINE_START_YEAR}&end={END_YEAR}&format=json'
                data = self._request_json(url)
            except (HTTPError, TimeoutError, OSError, ValueError):
                continue
            latest_by_country = {}
            for record in data.get('records', []):
                iso3, year, value = record.get('geoUnit'), record.get('year'), record.get('value')
                if iso3 not in countries or year is None or value is None:
                    continue
                if iso3 not in latest_by_country or year > latest_by_country[iso3][0]:
                    latest_by_country[iso3] = (year, value)
            filled = 0
            for iso3, (year, value) in latest_by_country.items():
                existing = prepared.get(iso3, {}).get(key)
                if existing is not None and self._valid(existing, config) and existing.get('year', 0) >= year:
                    continue
                if year < START_YEAR:
                    continue
                prepared.setdefault(iso3, {})[key] = {'raw': float(value), 'observations': 1, 'year': year}
                filled += 1
            if filled:
                self.stdout.write(f'UIS supplement filled {key} for {filled} economies missing it in WDI.')

    @staticmethod
    def _gdp_per_capita(iso3, prepared):
        gdp = prepared.get(iso3, {}).get('gdp_ppp')
        population = prepared.get(iso3, {}).get('population')
        if not gdp or not population or not population['raw']:
            return None
        return gdp['raw'] / population['raw']

    def _approximate_missing_values(self, prepared, countries, observations, eligible_keys):
        """The Compatriot Estimation Method: for a value with no real, current report anywhere,
        (1) look for the country's own most recent historical observation, however old, as a
        baseline; (2) find compatriot peers - same World Bank region, real current data, ranked
        by closeness in GDP per capita rather than the whole region indiscriminately; (3) if a
        baseline exists and those same compatriots have data at the baseline year, project the
        baseline forward by the compatriots' trend since that year; otherwise use the compatriots'
        current average directly. Devised at the user's direction, not an existing named method."""
        notes = []
        for key in eligible_keys:
            config = INDICATORS[key]
            real_countries = [
                iso3 for iso3, meta in countries.items()
                if key in prepared.get(iso3, {}) and self._valid(prepared[iso3][key], config)
                and not prepared[iso3][key].get('approximated')
            ]
            for iso3, meta in countries.items():
                value = prepared.get(iso3, {}).get(key)
                if value is not None and self._valid(value, config):
                    continue
                region_peers = [c for c in real_countries if countries[c]['region'] == meta['region']]
                if len(region_peers) < MIN_APPROXIMATION_PEERS:
                    continue
                target_gdp_pc = self._gdp_per_capita(iso3, prepared)
                if target_gdp_pc is not None:
                    region_peers.sort(key=lambda c: abs((self._gdp_per_capita(c, prepared) or target_gdp_pc) - target_gdp_pc))
                compatriots = region_peers[:COMPATRIOT_POOL_SIZE]
                peer_current_avg = statistics.fmean(prepared[c][key]['raw'] for c in compatriots)

                history = sorted(observations.get(iso3, {}).get(key, []), key=lambda item: item['year'])
                baseline = history[-1] if history else None
                estimated = peer_current_avg
                baseline_note = None
                if baseline:
                    peer_baseline_values = []
                    for c in compatriots:
                        match = [
                            item['value'] for item in observations.get(c, {}).get(key, [])
                            if item['year'] == baseline['year']
                        ]
                        if match:
                            peer_baseline_values.append(match[0])
                    peer_baseline_avg = statistics.fmean(peer_baseline_values) if peer_baseline_values else 0
                    if peer_baseline_values and not math.isclose(peer_baseline_avg, 0):
                        trend_ratio = peer_current_avg / peer_baseline_avg
                        estimated = baseline['value'] * trend_ratio
                        baseline_note = {
                            'value': round(baseline['value'], 3), 'year': baseline['year'],
                            'trend_ratio': round(trend_ratio, 3), 'projected': True,
                        }
                    else:
                        baseline_note = {'value': round(baseline['value'], 3), 'year': baseline['year'], 'projected': False}

                prepared.setdefault(iso3, {})[key] = {
                    'raw': estimated, 'observations': 0, 'approximated': True,
                    'approximation_method': 'Compatriot Estimation Method',
                    'approximation_basis': compatriots,
                }
                if baseline_note:
                    prepared[iso3][key]['historical_baseline'] = baseline_note
                detail = f' projected from a {baseline_note["year"]} baseline' if baseline_note and baseline_note['projected'] else ''
                notes.append(
                    f'{iso3}.{key} approximated via the Compatriot Estimation Method from {compatriots}{detail}.'
                )
        return notes

    def _military_data(self, countries, observations):
        military = {}
        for iso3 in countries:
            entry = {}
            for key in ('military_expenditure_gdp', 'armed_forces_personnel'):
                series = observations[iso3].get(key, [])
                if not series:
                    continue
                latest = max(series, key=lambda item: item['year'])
                entry[key] = {'raw': round(latest['value'], 3), 'year': latest['year']}
            military[iso3] = entry
        arms_data, vintage = self._fetch_sipri_arms_exports(countries)
        if not arms_data:
            arms_data, vintage = self._load_sipri_arms_exports_csv()
        for iso3, value in arms_data.items():
            if iso3 in military:
                military[iso3]['arms_export_tiv'] = value
        return military, vintage

    def _fetch_sipri_arms_exports(self, countries):
        name_lookup = {meta['name'].strip().lower(): iso3 for iso3, meta in countries.items()}
        body = {
            'filters': [
                {'field': 'Include top', 'oldField': '', 'condition': 'contains', 'value1': SIPRI_TOP_N, 'value2': '', 'listData': []},
                {'field': 'Year range 1', 'oldField': '', 'condition': 'contains', 'value1': START_YEAR, 'value2': END_YEAR, 'listData': []},
                {'field': 'orderbyseller', 'oldField': '', 'condition': '', 'value1': '', 'value2': '', 'listData': []},
                {'field': 'Status', 'oldField': '', 'condition': '', 'value1': '0', 'value2': '', 'listData': []},
                {'field': 'Main Suppliers', 'oldField': '', 'condition': '', 'value1': 0, 'value2': '', 'listData': []},
                {'field': 'PercentChange', 'oldField': '', 'condition': '', 'value1': '0', 'value2': '', 'listData': []},
                {'field': 'MovingAverage', 'oldField': '', 'condition': '', 'value1': False, 'value2': '', 'listData': []},
            ],
            'logic': 'AND',
        }
        try:
            payload = self._request_json(SIPRI_API, body)
        except (HTTPError, TimeoutError, OSError, ValueError, KeyError) as exc:
            self.stdout.write(self.style.WARNING(f'SIPRI live fetch failed ({exc}); trying manual CSV fallback.'))
            return {}, None
        csv_text = payload.get('result', '') if isinstance(payload, dict) else ''
        lines = csv_text.strip().split('\n')
        vintage = None
        for line in lines[:10]:
            if line.startswith('Data generated:'):
                vintage = line.split('Data generated:', 1)[1].strip()
            elif 'Data generated:' in line:
                vintage = line.split('Data generated:', 1)[1].strip()
        data, unmatched = {}, []
        for row in csv.reader(lines):
            if len(row) < 15 or not row[1].strip().isdigit():
                continue
            name_raw = row[3].strip()
            name_key = name_raw.rstrip('*').strip().lower()
            iso3 = name_lookup.get(name_key) or SIPRI_NAME_ALIASES.get(name_key)
            if not iso3 or iso3 not in countries:
                if name_raw and name_raw not in ('Others', 'Total'):
                    unmatched.append(name_raw)
                continue
            try:
                total = float(row[14])
            except (ValueError, IndexError):
                continue
            data[iso3] = {'raw': total, 'period': f'{START_YEAR}-{END_YEAR}', 'observations': 1}
        if data:
            self.stdout.write(self.style.SUCCESS(
                f'SIPRI live fetch matched {len(data)} economies to arms-export data (data as of {vintage}).'
            ))
        if unmatched:
            self.stdout.write(f'SIPRI suppliers not matched to a cohort economy: {sorted(set(unmatched))[:15]}')
        return data, vintage

    def _load_sipri_arms_exports_csv(self):
        if not SIPRI_CSV_PATH.is_file():
            self.stdout.write(self.style.WARNING(
                f'No SIPRI export file at {SIPRI_CSV_PATH} and the live SIPRI fetch failed; '
                'arms_export_tiv omitted from the military panel.'
            ))
            return {}, None
        data = {}
        vintage = None
        with SIPRI_CSV_PATH.open(newline='', encoding='utf-8') as handle:
            for row in csv.DictReader(handle):
                iso3 = (row.get('iso3') or '').strip().upper()
                if not iso3:
                    continue
                try:
                    value = float(row['tiv_value'])
                except (KeyError, ValueError, TypeError):
                    continue
                data[iso3] = {'raw': value, 'period': row.get('period', ''), 'observations': 1}
                vintage = row.get('data_as_of') or vintage
        return data, vintage

    def _score_model(self, model, pillars, prepared, cohort):
        input_keys = sorted({key for pillar in model['components'] for key in pillars[pillar]['inputs']})
        stats = {}
        for key in input_keys:
            real_values = [
                self._transform(prepared[iso3][key]['raw'], INDICATORS[key])
                for iso3 in cohort if not prepared[iso3][key].get('approximated')
            ]
            values = real_values if len(real_values) >= 2 else [
                self._transform(prepared[iso3][key]['raw'], INDICATORS[key]) for iso3 in cohort
            ]
            stats[key] = (statistics.fmean(values), statistics.pstdev(values))
        results = {}
        for iso3 in cohort:
            components = {}
            for pillar_key in model['components']:
                scored_inputs = {}
                for key in pillars[pillar_key]['inputs']:
                    value = prepared[iso3][key]
                    transformed = self._transform(value['raw'], INDICATORS[key])
                    centre, spread = stats[key]
                    z_value = 0 if math.isclose(spread, 0) else (transformed - centre) / spread
                    z_value *= INDICATORS[key].get('direction', 1)
                    scored_inputs[key] = {**self._public_value(value), 'z': round(z_value, 4)}
                pillar_z = statistics.fmean(item['z'] for item in scored_inputs.values())
                components[pillar_key] = {'z': round(pillar_z, 4), 'inputs': scored_inputs}
            score = statistics.fmean(item['z'] for item in components.values())
            results[iso3] = {'score': round(score, 4), 'components': components}
        ordered = sorted(results, key=lambda code: results[code]['score'], reverse=True)
        for rank, iso3 in enumerate(ordered, 1):
            results[iso3]['default_rank'] = rank
        return results

    def _trade_links(self, iso3, atlas, locations_by_id):
        eligible_edges = [
            edge for edge in atlas['bilateral'].get(iso3, [])
            if locations_by_id.get(edge['partner_id'], {}).get('iso3Code') in self._valid_iso3s
            and not locations_by_id.get(edge['partner_id'], {}).get('formerCountry')
        ]
        total = sum(edge['value'] for edge in eligible_edges)
        links = []
        for edge in sorted(eligible_edges, key=lambda item: item['value'], reverse=True):
            location = locations_by_id.get(edge['partner_id'])
            if (
                not location or location.get('iso3Code') not in self._valid_iso3s
                or location.get('formerCountry')
            ):
                continue
            links.append({
                'iso3': location['iso3Code'], 'name': location.get('nameShortEn') or location['iso3Code'],
                'value': round(edge['value'], 2), 'share': round(edge['value'] / total, 5) if total else 0,
            })
            if len(links) == 6:
                break
        return links

    @staticmethod
    def _valid(value, config):
        if config.get('transform') == 'log10' and value['raw'] <= 0:
            return False
        if (
            config['aggregation'] == 'latest' and value.get('year', 0) < MIN_LATEST_YEAR
            and not value.get('approximated') and not config.get('ignore_recency')
        ):
            return False
        return math.isfinite(value['raw'])

    @staticmethod
    def _transform(value, config):
        if config.get('transform') == 'log10':
            return math.log10(value)
        if config.get('transform') == 'log1p':
            return math.log1p(value)
        return value

    @staticmethod
    def _public_value(value):
        public = {'raw': round(value['raw'], 3), 'observations': value['observations']}
        for key in ('year', 'start_year', 'end_year'):
            if key in value:
                public[key] = value[key]
        if value.get('approximated'):
            public['approximated'] = True
            public['approximation_method'] = value.get('approximation_method', '')
            public['approximation_basis'] = value.get('approximation_basis', [])
            if 'historical_baseline' in value:
                public['historical_baseline'] = value['historical_baseline']
        return public

    def _request_world_bank(self, path, **params):
        query = urlencode({'format': 'json', 'per_page': 20000, **params})
        payload = self._request_json(f'{WORLD_BANK_API}/{path}?{query}')
        if not isinstance(payload, list) or len(payload) < 2:
            raise ValueError(f'Unexpected World Bank response for {path}')
        return payload

    def _country_metadata(self):
        payload = self._request_world_bank('country')
        countries = {}
        for row in payload[1]:
            region = row.get('region') or {}
            iso3 = row.get('id')
            if not iso3 or region.get('id') == 'NA':
                continue
            countries[iso3] = {
                'name': row['name'], 'region': region['value'], 'iso2': row.get('iso2Code'),
            }
        return countries

    def _world_bank_observations(self, countries):
        observations = defaultdict(lambda: defaultdict(list))
        updated_dates = []
        for key, config in INDICATORS.items():
            if 'id' not in config:
                continue
            self.stdout.write(f'Downloading {config["label"]}...')
            start = BASELINE_START_YEAR if config.get('approximable') else START_YEAR
            payload = self._request_world_bank(
                f'country/all/indicator/{config["id"]}', date=f'{start}:{END_YEAR}',
            )
            updated_dates.append(payload[0].get('lastupdated'))
            for row in payload[1]:
                iso3, value = row.get('countryiso3code'), row.get('value')
                if iso3 in countries and value is not None:
                    observations[iso3][key].append({'year': int(row['date']), 'value': float(value)})
        return observations, updated_dates

    def _atlas_data(self):
        self.stdout.write('Downloading Harvard Atlas complexity and bilateral trade...')
        query = f'''{{
          locationCountry {{ countryId iso3Code nameShortEn formerCountry }}
          countryYear(productClass: HS92, yearMin: {ATLAS_YEAR}, yearMax: {ATLAS_YEAR})
            {{ countryId year exportValue importValue eci }}
          countryCountryYear(productClass: HS92, yearMin: {ATLAS_YEAR}, yearMax: {ATLAS_YEAR})
            {{ countryId partnerCountryId exportValue }}
          productHs92(productLevel: 2) {{ productId code }}
          countryProductYear(productClass: HS92, productLevel: 2, yearMin: {ATLAS_YEAR}, yearMax: {ATLAS_YEAR})
            {{ countryId productId exportValue }}
        }}'''
        payload = self._request_json(ATLAS_API, {'query': query})
        if payload.get('errors'):
            raise ValueError(payload['errors'])
        data = payload['data']
        locations_by_id = {row['countryId']: row for row in data['locationCountry']}
        iso_by_id = {key: row.get('iso3Code') for key, row in locations_by_id.items()}
        country_year = {}
        for row in data['countryYear']:
            iso3 = iso_by_id.get(row['countryId'])
            if iso3:
                country_year[iso3] = row
        bilateral = defaultdict(list)
        for row in data['countryCountryYear']:
            iso3 = iso_by_id.get(row['countryId'])
            value = row.get('exportValue') or 0
            if iso3 and value > 0:
                bilateral[iso3].append({'partner_id': row['partnerCountryId'], 'value': float(value)})
        resource_chapters = {'25', '26', '27', '44', '71'}
        natural_resource_products = {
            row['productId'] for row in data['productHs92'] if row.get('code') in resource_chapters
        }
        products = defaultdict(dict)
        for row in data['countryProductYear']:
            iso3 = iso_by_id.get(row['countryId'])
            value = row.get('exportValue') or 0
            if iso3 and value > 0:
                products[iso3][row['productId']] = float(value)
        return {
            'locations_by_id': locations_by_id, 'country_year': country_year,
            'bilateral': bilateral, 'natural_resource_products': natural_resource_products,
            'products': products,
        }

    def _request_json(self, url, body=None):
        data = json.dumps(body).encode('utf-8') if body else None
        headers = {'User-Agent': 'World-Ledger/1.0 (+https://accidentalscientist.com)'}
        if body:
            headers['Content-Type'] = 'application/json'
        request = Request(url, data=data, headers=headers)
        for attempt in range(4):
            try:
                with urlopen(request, timeout=180) as response:
                    return json.load(response)
            except (HTTPError, TimeoutError, OSError):
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
