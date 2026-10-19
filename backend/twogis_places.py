"""Live 2GIS text search. Never expose a request URL containing the API key."""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import math
import re

import httpx

from backend.config import BBOX, CATEGORIES, settings
from backend.live_places import LiveSearchError, MemoryPlaces
from backend.recommend import interpret, recommend
from backend.models import RecommendationRequest

URL = 'https://catalog.api.2gis.com/3.0/items'


class TwoGISSearchError(LiveSearchError):
    def __init__(self, message):
        self.public_message = message
        super().__init__(message)


def queries_for(request, intent):
    if request.interests:
        return [CATEGORIES[k] for k in request.interests]
    if intent and intent.name_query:
        return [intent.name_query]
    if intent and intent.cuisines:
        return [request.query]  # Keep food specificity; don't replace sushi with all restaurants.
    if intent and intent.place_label:
        return [intent.place_label]
    if intent and intent.categories:
        return [CATEGORIES[k] for k in intent.categories]
    if (intent and intent.general) or not request.query.strip():
        return ['Парки', 'Достопримечательности', 'Кафе']
    return [request.query]  # Native text search is not limited to our quick filters or OSM tags.


def normalize_items(items):
    collected = datetime.now(timezone.utc).isoformat()
    pois, seen = [], set()
    for item in items:
        if not isinstance(item, dict):
            continue
        identifier, name, point = item.get('id'), item.get('name'), item.get('point')
        if not isinstance(identifier, str) or not re.fullmatch(r'\d{1,30}', identifier) or identifier in seen or not isinstance(name, str) or not name.strip() or not isinstance(point, dict):
            continue
        lat, lon = point.get('lat'), point.get('lon')
        if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in (lat, lon)):
            continue
        if not (BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3]):
            continue
        seen.add(identifier)
        raw_rubrics = item.get('rubrics')
        rubrics = [r for r in (raw_rubrics if isinstance(raw_rubrics, list) else []) if isinstance(r, dict) and isinstance(r.get('name'), str)]
        labels = [r['name'] for r in rubrics]
        primary = next((r for r in rubrics if r.get('kind') == 'primary'), rubrics[0] if rubrics else {})
        label = primary.get('name', item.get('purpose_name') or 'Место')
        # Classification uses provider rubrics, never the user's requested type as fabricated evidence.
        rubric_request = RecommendationRequest(query=' '.join(labels)[:600], latitude=lat, longitude=lon)
        kinds = interpret(rubric_request)['interests']
        kind = 'computer_club' if any(r.get('id') == '178' or r.get('alias') == 'kompyuternye_kluby' for r in rubrics) else (kinds[0] if kinds else '2gis:' + str(primary.get('id', 'place')))
        address = item.get('address_name') if isinstance(item.get('address_name'), str) else None
        source = {'id': '2gis:' + identifier + ':attributes', 'name': '2ГИС',
            'url': 'https://2gis.kz/astana/firm/' + identifier,
            'collected_at': collected, 'license': '2GIS API terms',
            'fields': {'rubrics': '; '.join(labels)},
            'sha256': hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()}
        pois.append({'id': '2gis:' + identifier, 'name': name, 'names': {},
            'latitude': lat, 'longitude': lon, 'coordinate_accuracy': 'point',
            'categories': [kind], 'category_label': label, 'tags': {},
            'description': label + (f'. Адрес: {address}.' if address else '.'), 'description_origin': 'derived_from_provider',
            'address': address, 'opening_hours_raw': None, 'timezone': 'Asia/Almaty',
            'wheelchair': None, 'sockets': None, 'child_friendly': None,
            'sources': [source], 'collected_at': collected, 'source_updated_at': None,
            'data_quality_flags': ['missing_opening_hours'], 'provider_search_match': True})
    return {'pois': pois, 'version': hashlib.sha256(json.dumps(pois, sort_keys=True).encode()).hexdigest()[:16]}


async def find_twogis(request, intent):
    if not (BBOX[0] <= request.latitude <= BBOX[2] and BBOX[1] <= request.longitude <= BBOX[3]):
        return None
    queries = list(dict.fromkeys(queries_for(request, intent)))
    semaphore = asyncio.Semaphore(4)
    try:
        async with asyncio.timeout(14):
            async with httpx.AsyncClient(timeout=10) as client:
                async def fetch(query, page):
                    async with semaphore:
                        response = await client.get(URL, params={'key': settings.twogis_api_key, 'q': query,
                            'point': f'{request.longitude},{request.latitude}', 'radius': request.radius_m,
                            'sort': 'distance', 'page_size': 5, 'page': page, 'fields': 'items.point,items.rubrics'})
                        data = response.json()
                        if not isinstance(data, dict) or not isinstance(data.get('meta'), dict):
                            raise ValueError('Invalid metadata')
                        code = data.get('meta', {}).get('code', response.status_code)
                        if code in (401, 403):
                            raise TwoGISSearchError('2ГИС: проверьте ключ, доступ Places API и ограничения ключа в кабинете.')
                        if code in (402, 429):
                            raise TwoGISSearchError('2ГИС: достигнут лимит запросов или закончился доступ к API.')
                        if code == 404:
                            return [], 0
                        if code != 200 or response.status_code != 200:
                            raise TwoGISSearchError('2ГИС временно недоступен. Повторите поиск позже.')
                        result = data.get('result', {})
                        if not isinstance(result, dict) or not isinstance(result.get('items'), list):
                            raise ValueError('Invalid items')
                        return result['items'], int(result.get('total', 0))
                first = await asyncio.gather(*(fetch(q, 1) for q in queries))
                items = [item for batch, _ in first for item in batch]
                total = sum(count for _, count in first)
                # Demo keys support five records per page. Bound pages and credits per submission.
                if len(queries) == 1:
                    pages = min(3, math.ceil(min(total, request.limit) / 5))
                    rest = await asyncio.gather(*(fetch(queries[0], page) for page in range(2, pages + 1)))
                    items.extend(item for batch, _ in rest for item in batch)
        places = MemoryPlaces(normalize_items(items))
        places.mode = 'live_2gis'
        result = recommend(request, places, places, intent)
        result.update(mode='live', data_mode='live', place_provider='2ГИС',
            checked_at=datetime.now(timezone.utc).isoformat(), live_objects_count=len(places.pois), provider_total=total)
        if total > len(places.pois):
            result['warnings'].append(f'2ГИС нашёл объектов: {total}. Проверены ближайшие {len(places.pois)}; показаны прошедшие ваши условия.')
        if result['empty_reason']:
            result['empty_reason'] = (('2ГИС нашёл места, но они не прошли выбранные ограничения времени или фильтры. Увеличьте время или измените условия.' if request.time_enabled else '2ГИС нашёл места, но они не прошли выбранные фильтры. Измените условия поиска.') if places.pois else f'2ГИС не вернул мест по этому запросу в радиусе {request.radius_m / 1000:g} км. Попробуйте уточнить запрос или увеличить радиус.')
        return result
    except TwoGISSearchError:
        raise
    except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError):
        raise TwoGISSearchError('Не удалось получить места из 2ГИС. Проверьте соединение и повторите поиск.') from None
