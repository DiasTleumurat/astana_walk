"""Fetch fresh, georeferenced POIs on submit. No model-generated coordinates."""
import asyncio
from datetime import datetime, timezone
import json
import re
import logging
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

from backend.config import BBOX
from backend.recommend import interpret, recommend
from backend.storage import document
from ingestion.cli import normalize

ENDPOINTS = ('https://maps.mail.ru/osm/tools/overpass/api/interpreter', 'https://overpass.private.coffee/api/interpreter')
FILTERS = {
    'park': '["leisure"~"^(park|garden)$"]', 'cafe': '["amenity"="cafe"]',
    'museum': '["tourism"="museum"]', 'gallery': '["tourism"="gallery"]',
    'attraction': '["tourism"="attraction"]', 'viewpoint': '["tourism"="viewpoint"]',
    'playground': '["leisure"="playground"]', 'public_space': '["place"="square"]',
    'computer_club': '["amenity"~"^(internet_cafe|gaming_centre|lan_gaming_centre)$"]',
    'restaurant': '["amenity"~"^(restaurant|fast_food|food_court)$"]',
    'cinema': '["amenity"="cinema"]', 'shopping_mall': '["shop"="mall"]',
    'library': '["amenity"="library"]', 'fitness': '["leisure"~"^(fitness_centre|sports_centre)$"]',
}


class LiveSearchError(Exception):
    pass


class MemoryPlaces:
    mode = 'live_osm'

    def __init__(self, data):
        self.pois = data['pois']
        self.by_id = {p['id']: p for p in self.pois}
        self.version = data['version']

    def rank(self, query, allowed):
        words = set(re.findall(r'\w{3,}', query.casefold()))
        return {p['id']: sum(w in document(p).casefold() for w in words) / max(1, len(words)) / 20
                for p in self.pois if p['id'] in allowed}


def build_query(request, intent):
    kinds = request.interests or (intent.categories if intent else interpret(request)['interests'])
    if intent and intent.unsupported and not intent.osm_filters:
        return None
    if intent and intent.osm_filters and not request.interests:
        bbox = ','.join(map(str, BBOX))
        selectors = []
        for tag in intent.osm_filters:
            key, value = tag.split(':', 1)
            selectors.append(f'nwr[{json.dumps(key)}={json.dumps(value)}]({bbox});')
        return '[out:json][timeout:20];(' + ''.join(selectors) + ');out center meta;'
    if not kinds:
        if intent and intent.name_query:
            kinds = list(FILTERS)
        elif not request.query.strip() or (intent and intent.general):
            kinds = ['park', 'attraction', 'public_space', 'cafe']
        else:
            return None
    bbox = ','.join(map(str, BBOX))  # City bounds, never the visitor's precise coordinate.
    selectors = [f'nwr{FILTERS[k]}({bbox});' for k in kinds if k in FILTERS]
    if 'computer_club' in kinds:
        for key in ('name', 'name:ru', 'name:en', 'brand'):
            selectors.append(f'nwr[{json.dumps(key)}~"компьютерн.*клуб|кибер.*клуб|colizeum|cyber.?x|cyber.?arena",i]({bbox});')
    return '[out:json][timeout:20];(' + ''.join(selectors) + ');out center meta;'


async def find_live(request, intent):
    query = build_query(request, intent)
    if query is None:
        return None
    if not (BBOX[0] <= request.latitude <= BBOX[2] and BBOX[1] <= request.longitude <= BBOX[3]):
        return None
    try:
        async with asyncio.timeout(48):
            async with httpx.AsyncClient(timeout=23, headers={'User-Agent': 'AstanaWalk/0.1 (live POI search)', 'Cache-Control': 'no-cache'}) as client:
                for endpoint in ENDPOINTS:
                    try:
                        response = await client.post(endpoint, data={'data': query})
                        response.raise_for_status()
                        raw = response.json()
                        if 'remark' in raw or not isinstance(raw.get('elements'), list):
                            raise ValueError('Partial or invalid data')
                        checked_at = datetime.now(timezone.utc).isoformat()
                        raw.update(_collected_at=checked_at, _endpoint=endpoint, _query=query)
                        if intent and intent.osm_filters:
                            for element in raw['elements']:
                                for tag in intent.osm_filters:
                                    key, value = tag.split(':', 1)
                                    if element.get('tags', {}).get(key) == value:
                                        element.update(_place_kind=f'osm:{key}:{value}', _place_label=intent.place_label or value.replace('_', ' '))
                                        break
                        data = normalize(raw, allow_generic=bool(intent and intent.osm_filters))
                        places = MemoryPlaces(data)
                        result = recommend(request, places, places, intent)
                        result.update(mode='live', data_mode='live', checked_at=checked_at, live_objects_count=len(places.pois))
                        if result['empty_reason']:
                            result['empty_reason'] = 'Онлайн-поиск OpenStreetMap выполнен, но в выбранном радиусе и времени подходящих объектов не найдено. Увеличьте радиус или время; покрытие источника может быть неполным.'
                        return result
                    except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
                        logger.warning('Live place source %s failed: %s (HTTP %s)', urlparse(endpoint).hostname,
                                       type(error).__name__, getattr(getattr(error, 'response', None), 'status_code', None))
                        continue
    except TimeoutError:
        pass
    raise LiveSearchError('Live source unavailable')
