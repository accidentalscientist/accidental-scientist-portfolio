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
START_YEAR = 2015
END_YEAR = 2024
ATLAS_YEAR = 2024
MIN_OBSERVATIONS = 5
MIN_LATEST_YEAR = 2020
COHORT_SIZE = 48

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
}

PILLARS = {
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

MODELS = {
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


class Command(BaseCommand):
    help = 'Build World Ledger Giga Dataset version 1.0.'

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
        all_inputs = sorted({key for pillar in PILLARS.values() for key in pillar['inputs']})
        complete = [
            iso3 for iso3 in countries
            if all(key in prepared[iso3] and self._valid(prepared[iso3][key], INDICATORS[key]) for key in all_inputs)
        ]
        if len(complete) < COHORT_SIZE:
            raise CommandError(f'Only {len(complete)} economies have complete Giga v1 coverage; {COHORT_SIZE} required.')

        provisional = self._score_model(MODELS['power'], prepared, complete)
        cohort = sorted(complete, key=lambda code: provisional[code]['score'], reverse=True)[:COHORT_SIZE]
        if 'CHN' not in cohort or 'IND' not in cohort:
            raise CommandError('The materiality rule unexpectedly excluded China or India.')

        model_results = {key: self._score_model(model, prepared, cohort) for key, model in MODELS.items()}
        atlas_by_id = atlas['locations_by_id']
        output_countries = []
        for iso3 in sorted(cohort, key=lambda code: countries[code]['name']):
            links = self._trade_links(iso3, atlas, atlas_by_id)
            output_countries.append({
                'iso3': iso3,
                'name': countries[iso3]['name'],
                'region': countries[iso3]['region'],
                'models': {key: model_results[key][iso3] for key in MODELS},
                'trade_links': links,
            })

        payload = {
            'meta': {
                'product': 'World Ledger', 'dataset': 'Giga Dataset version 1.0',
                'data_updated': max(date for date in updated_dates if date),
                'atlas_year': ATLAS_YEAR, 'cohort_count': COHORT_SIZE,
                'score_start': START_YEAR, 'score_end': END_YEAR,
                'minimum_observations': MIN_OBSERVATIONS, 'minimum_latest_year': MIN_LATEST_YEAR,
                'inclusion_rule': 'Complete coverage on every Giga v1 input, then the top 48 economies under equal-weight Power Now.',
                'models': MODELS, 'pillars': PILLARS, 'indicators': INDICATORS,
                'sources': [
                    {'name': 'World Development Indicators', 'url': 'https://databank.worldbank.org/source/world-development-indicators'},
                    {'name': 'Worldwide Governance Indicators', 'url': 'https://www.worldbank.org/en/publication/worldwide-governance-indicators'},
                    {'name': 'Harvard Growth Lab Atlas of Economic Complexity', 'url': 'https://atlas.hks.harvard.edu/data-downloads/'},
                ],
            },
            'countries': output_countries,
        }
        destination = Path(__file__).resolve().parents[2] / 'data' / 'world_lens.json'
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        names = ', '.join(code for code in cohort)
        self.stdout.write(self.style.SUCCESS(f'Wrote {COHORT_SIZE} complete-coverage economies to {destination}'))
        self.stdout.write(f'Cohort: {names}')

    def _prepare_world_bank(self, countries, observations):
        prepared = defaultdict(dict)
        for iso3 in countries:
            for key, config in INDICATORS.items():
                if 'id' not in config:
                    continue
                series = observations[iso3].get(key, [])
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

    def _score_model(self, model, prepared, cohort):
        input_keys = sorted({key for pillar in model['components'] for key in PILLARS[pillar]['inputs']})
        stats = {}
        for key in input_keys:
            values = [self._transform(prepared[iso3][key]['raw'], INDICATORS[key]) for iso3 in cohort]
            stats[key] = (statistics.fmean(values), statistics.pstdev(values))
        results = {}
        for iso3 in cohort:
            components = {}
            for pillar_key in model['components']:
                scored_inputs = {}
                for key in PILLARS[pillar_key]['inputs']:
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
        if config['aggregation'] == 'latest' and value.get('year', 0) < MIN_LATEST_YEAR:
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
            countries[iso3] = {'name': row['name'], 'region': region['value']}
        return countries

    def _world_bank_observations(self, countries):
        observations = defaultdict(lambda: defaultdict(list))
        updated_dates = []
        for key, config in INDICATORS.items():
            if 'id' not in config:
                continue
            self.stdout.write(f'Downloading {config["label"]}...')
            payload = self._request_world_bank(
                f'country/all/indicator/{config["id"]}', date=f'{START_YEAR}:{END_YEAR}',
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
