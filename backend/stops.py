"""An optional stop on the way to each recommended place ("и по пути купить берлинеры").

The main search runs on the wish without the stop part; stop candidates come from
the same provider family and are attached only when the detour fits the time limit.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import json
import math
import re

import httpx

from backend.config import BBOX, settings
from backend.hours import visit_status
from backend.intent import resolve_intent
from backend.live_places import LiveSearchError
from backend.models import RecommendationRequest
from backend.recommend import distance_m, rating_of, rating_score
from backend.twogis_places import fetch_page, normalize_items
from ingestion.cli import normalize

STOP_MINUTES = 10
# One rating point above the prior is worth this many metres of detour.
RATING_METRES = 150
_SPLIT = re.compile(r'[\s,;]*(?:(?:а|и|ну)\s+)?(?:по\s+пути|по\s+дороге|заодно|попутно)(?:\s+(?:туда|к\s+нему|к\s+ней))?[\s,:]+', re.I)
_VERBS = re.compile(r'^(?:(?:хочу|хотелось бы|надо|нужно|бы)\s+)*(?:купить|взять|захватить|забрать|выпить|съесть|поесть|перекусить|попить|зайти|заглянуть|заскочить)\s+(?:(?:в|за|на)\s+)?', re.I)
# Common errands: stems -> (label, OSM tags, 2GIS rubric queries next to the wish text).
KINDS = (
    (('пончик', 'берлинер', 'донат', 'выпечк', 'пекарн', 'булоч', 'круассан', 'кондитер', 'пирожн', 'торт', 'эклер', 'десерт', 'синнабон'),
     'Пекарня или кондитерская', ['shop:bakery', 'shop:pastry', 'shop:confectionery', 'cuisine:donut'], ['Пекарни', 'Кондитерские']),
    (('кофе', 'капучино', 'латте', 'раф', 'кофейн'), 'Кофейня', ['amenity:cafe'], ['Кофейни']),
    (('мороженое', 'мороженн', 'пломбир'), 'Мороженое', ['shop:ice_cream', 'amenity:ice_cream'], ['Мороженое']),
    (('цветы', 'цветов', 'букет'), 'Цветы', ['shop:florist'], ['Цветы']),
    (('вод', 'продукт', 'перекус', 'снек', 'попить'), 'Магазин продуктов', ['shop:convenience', 'shop:supermarket'], ['Продуктовые магазины']),
    (('аптек', 'лекарств'), 'Аптека', ['amenity:pharmacy'], ['Аптеки']),
)
OVERPASS = ('https://maps.mail.ru/osm/tools/overpass/api/interpreter', 'https://overpass.private.coffee/api/interpreter')


def split_stop(query):
    """Return (main wish, stop text) or None when the wish has no "on the way" part."""
    match = _SPLIT.search(query)
    if not match:
        return None
    main, stop = query[:match.start()].strip(' ,.;'), query[match.end():].strip(' ,.!?;')
    if not main or not stop:
        return None
    return main, stop


def stop_spec(stop):
    """Search text, label and OSM tags for the stop part of a wish."""
    text = stop.casefold().replace('ё', 'е')
    query = _VERBS.sub('', re.sub(r'\([^)]*\)', ' ', stop)).strip(' ,.!?') or stop
    for stems, label, tags, rubrics in KINDS:
        if any(re.search(r'(?<!\w)' + stem, text) for stem in stems):
            return {'query': query[:100], 'label': label, 'osm_filters': tags, 'rubrics': rubrics}
    return {'query': query[:100], 'label': query[:1].upper() + query[1:100], 'osm_filters': [], 'rubrics': []}


def matches(poi, tags):
    for tag in tags:
        key, value = tag.split(':', 1)
        if value in (v.strip() for v in str(poi.get('tags', {}).get(key, '')).split(';')):
            return True
        if tag == 'amenity:cafe' and poi['categories'][0] == 'cafe':
            return True
    return False


def walk_minutes(metres):
    return max(1, math.ceil(metres / 1000 / settings.walk_speed_kmh * 60 * settings.walk_detour_factor))


def attach_stops(result, request, spec, candidates):
    """Pick, for every place, the stop with the smallest detour that fits the time limit."""
    rules = result['applied_constraints']
    now = request.starts_at or datetime.now(timezone.utc)
    result['stop_request'] = {'label': spec['label'], 'query': spec['query']}
    places = result['recommendations']
    if not places:
        return result
    if not candidates:
        result['warnings'].append(f'По пути не нашлось: «{spec["query"]}» в радиусе поиска. Места показаны без остановки.')
        return result
    for place in places:
        best = None
        for stop in candidates:
            if stop['id'] == place['poi_id']:
                continue
            to_stop = distance_m(request.latitude, request.longitude, stop['latitude'], stop['longitude'])
            onward = distance_m(stop['latitude'], stop['longitude'], place['latitude'], place['longitude'])
            if to_stop > rules['radius_m']:
                continue
            walking = walk_minutes(to_stop) + walk_minutes(onward)
            total = walking + STOP_MINUTES + place['visit_minutes'] + (walk_minutes(place['distance_m']) if rules['return_to_start'] else 0)
            if rules['time_enabled'] and total > rules['minutes']:
                continue
            status = visit_status(stop.get('opening_hours_raw'), now + timedelta(minutes=walk_minutes(to_stop)), STOP_MINUTES)
            if status == 'closed':
                continue
            detour = to_stop + onward - place['distance_m']
            score = detour - RATING_METRES * rating_score(stop)
            if best is None or score < best[0]:
                best = (score, stop, to_stop, detour, walking, total, status)
        if best is None:
            continue
        _, stop, to_stop, detour, walking, total, status = best
        extra = max(0, total - place['total_minutes'])
        place['stop'] = {
            'poi_id': stop['id'], 'name': stop['name'], 'category_label': stop.get('category_label') or spec['label'],
            'latitude': stop['latitude'], 'longitude': stop['longitude'], 'address': stop.get('address'),
            'distance_m': round(to_stop), 'detour_m': round(max(0, detour)), 'walk_minutes': walk_minutes(to_stop),
            'visit_minutes': STOP_MINUTES, 'extra_minutes': extra, 'opening_status': status,
            'rating': rating_of(stop), 'sources': stop['sources'],
        }
        place['walk_minutes'], place['total_minutes'] = walking, total
        # The stop has its own block on the card; only the time estimate changes here.
        place['reason'] = re.sub(r'Оценка посещения с дорогой: \d+ мин\.', f'Оценка с остановкой по пути: {total} мин.', place['reason'])
    with_stop = [p for p in places if p.get('stop')]
    if not with_stop:
        result['warnings'].append(f'«{spec["query"]}» по пути есть, но с остановкой маршрут не укладывается во время. Увеличьте время или радиус.')
    # Places that satisfy the whole wish go first; the order inside each group is kept.
    result['recommendations'] = with_stop + [p for p in places if not p.get('stop')]
    return result


async def twogis_candidates(request, spec):
    queries = list(dict.fromkeys([spec['query'], *spec['rubrics']]))
    async with asyncio.timeout(10):
        async with httpx.AsyncClient(timeout=8) as client:
            pages = await asyncio.gather(*(fetch_page(client, request, query) for query in queries))
    return normalize_items([item for items, _ in pages for item in items])['pois']


async def overpass_candidates(spec):
    bbox = ','.join(map(str, BBOX))  # City bounds, never the visitor's precise coordinate.
    selectors = []
    for tag in spec['osm_filters']:
        key, value = tag.split(':', 1)
        test = f'[{json.dumps(key)}~"(^|;){value}(;|$)"]' if key == 'cuisine' else f'[{json.dumps(key)}={json.dumps(value)}]'
        selectors.append(f'nwr{test}({bbox});')
    query = '[out:json][timeout:15];(' + ''.join(selectors) + ');out center meta;'
    async with asyncio.timeout(25):
        async with httpx.AsyncClient(timeout=12, headers={'User-Agent': 'AstanaWalk/0.1 (live POI search)'}) as client:
            for endpoint in OVERPASS:
                try:
                    response = await client.post(endpoint, data={'data': query})
                    response.raise_for_status()
                    raw = response.json()
                    if not isinstance(raw.get('elements'), list):
                        raise ValueError('Invalid data')
                except (httpx.HTTPError, ValueError):
                    continue
                for element in raw['elements']:
                    element.update(_place_kind='stop', _place_label=spec['label'])
                raw['_collected_at'] = datetime.now(timezone.utc).isoformat()
                return normalize(raw, allow_generic=True)['pois']
    return None


async def find_candidates(request, spec, store):
    """2GIS text search when keyed, else live OSM tags, else the saved catalog."""
    if request.use_ai and settings.live_place_search:
        try:
            if settings.twogis_api_key:
                return await twogis_candidates(request, spec)
            if spec['osm_filters']:
                live = await overpass_candidates(spec)
                if live is not None:
                    return live
        except (LiveSearchError, httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError):
            pass  # A failed stop search never fails the main recommendation.
    return [p for p in store.pois if matches(p, spec['osm_filters'])]


async def resolve_stop(request, stop):
    """Unknown errands go to the intent model for OSM tags; no model, no stop."""
    intent = await resolve_intent(RecommendationRequest(query=stop, latitude=request.latitude, longitude=request.longitude))
    if intent is None or not intent.osm_filters:
        return None
    return {'osm_filters': intent.osm_filters, 'label': intent.place_label or stop}


async def stop_candidates(request, stop, store):
    """Independent of the main places, so it can run while they are searched."""
    spec = stop_spec(stop)
    if not spec['osm_filters'] and not settings.twogis_api_key:
        resolved = await resolve_stop(request, stop)
        if resolved:
            spec.update(resolved)
    return spec, await find_candidates(request, spec, store)
