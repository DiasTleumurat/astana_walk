"""Request-time OSRMRoute POIs; credentials and provider payloads stay server-side."""
import asyncio
import hashlib
import re
from datetime import datetime, timezone

import httpx

from backend.config import BBOX, settings
from backend.intent import Intent
from backend.live_places import LiveSearchError, MemoryPlaces
from backend.recommend import interpret, recommend
from ingestion.cli import normalize

URL = 'https://osrmroute.com/api/1/places'
TAGS = {
    'park': ['leisure:park', 'leisure:garden'], 'cafe': ['amenity:cafe'],
    'museum': ['tourism:museum'], 'gallery': ['tourism:gallery'],
    'attraction': ['tourism:attraction'], 'viewpoint': ['tourism:viewpoint'],
    'playground': ['leisure:playground'], 'public_space': ['place:square'],
    'computer_club': ['amenity:internet_cafe', 'amenity:gaming_centre', 'amenity:lan_gaming_centre', 'leisure:gaming_centre'],
    'restaurant': ['amenity:restaurant', 'amenity:fast_food', 'amenity:food_court'],
    'cinema': ['amenity:cinema'], 'shopping_mall': ['shop:mall'],
    'library': ['amenity:library'], 'fitness': ['leisure:fitness_centre', 'leisure:sports_centre'],
}


class OSRMSearchError(LiveSearchError):
    def __init__(self, message):
        self.public_message = message
        super().__init__(message)


def local_place_intent(request):
    """Fast common nouns; all other types are resolved by Gemini, not rejected."""
    text = re.sub(r'[.!?]', '', request.query.casefold()).strip()
    text = re.sub(r'^(?:(?:хочу|найди|найдите|покажи|ищу)(?: мне)?\s+)?(?:в\s+)?', '', text)
    text = re.sub(r'\s+(?:рядом|поблизости|рядом со мной)$', '', text)
    if not request.interests and re.fullmatch(r'(?:комп(?:ьютерн\w*)?|кибер)\s*клуб\w*', text):
        parsed = Intent(categories=['computer_club'], excluded=[], name_query='', unsupported='', general=False,
                        osm_filters=TAGS['computer_club'], place_label='Компьютерный клуб')
        parsed._method = 'local'
        return parsed
    aliases = {
        'стадион': ('leisure:stadium', 'Стадион'), 'аптека': ('amenity:pharmacy', 'Аптека'),
        'больница': ('amenity:hospital', 'Больница'), 'клиника': ('amenity:clinic', 'Клиника'),
        'парикмахерская': ('shop:hairdresser', 'Парикмахерская'),
        'автомойка': ('amenity:car_wash', 'Автомойка'), 'банкомат': ('amenity:atm', 'Банкомат'),
        'супермаркет': ('shop:supermarket', 'Супермаркет'), 'бассейн': ('leisure:swimming_pool', 'Бассейн'),
    }
    if not request.interests and text in aliases:
        tag, label = aliases[text]
        parsed = Intent(categories=[], excluded=[], name_query='', unsupported='', general=False,
                        osm_filters=[tag], place_label=label)
        parsed._method = 'local'
        return parsed
    return None


def normalize_places(items, intent=None):
    elements = []
    for item in items:
        if not isinstance(item, dict):
            continue
        point = item.get('point') or {}
        name, category, kind = item.get('name'), item.get('category'), item.get('type')
        if not isinstance(category, str) or not isinstance(kind, str) or not re.fullmatch(r'[a-z][a-z0-9_]*:[a-z][a-z0-9_]*', f'{category}:{kind}'):
            continue
        if not isinstance(name, str):
            name = ''
        lat, lon = point.get('lat'), point.get('lng')
        if isinstance(lat, bool) or isinstance(lon, bool) or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        identifier = int(hashlib.sha256(f'{name}|{lat}|{lon}'.encode()).hexdigest()[:14], 16)
        # Only source attributes become tags; missing hours/accessibility remain unknown.
        tags = {category: kind, 'name': name}
        source_tags = item.get('tags')
        for key, value in (source_tags if isinstance(source_tags, dict) else {}).items():
            if isinstance(key, str) and isinstance(value, str):
                tags[key] = value
        for source_key, tag_key in [('street', 'addr:street'), ('housenumber', 'addr:housenumber')]:
            if isinstance(item.get(source_key), str):
                tags[tag_key] = item[source_key]
        osm_id, osm_type = item.get('osm_id'), item.get('osm_type')
        valid_osm = isinstance(osm_id, int) and not isinstance(osm_id, bool) and osm_id > 0 and osm_type in ('node', 'way', 'relation')
        elements.append({'type': osm_type if valid_osm else 'node', 'id': osm_id if valid_osm else identifier,
                         'lat': lat, 'lon': lon, 'tags': tags, '_provider_only': not valid_osm,
                         '_place_kind': f'osm:{category}:{kind}',
                         '_place_label': intent.place_label if intent and f'{category}:{kind}' in intent.osm_filters and intent.place_label else kind.replace('_', ' ')})
    data = normalize({'elements': elements}, allow_generic=True)
    real_ids = {f"osm:{e['type']}:{e['id']}" for e in elements if not e['_provider_only']}
    for poi in data['pois']:
        if poi['id'] in real_ids:
            poi['sources'][0]['name'] = 'OpenStreetMap · через OSRMRoute'
            continue
        identifier = poi['id'].replace('osm:node:', 'osrmroute:')
        poi['id'] = identifier
        source = poi['sources'][0]
        source.update(id=identifier + ':attributes', name='OSRMRoute · OpenStreetMap',
                      url='https://osrmroute.com/docs#places')
    return data


async def find_osrm(request, intent):
    if not (BBOX[0] <= request.latitude <= BBOX[2] and BBOX[1] <= request.longitude <= BBOX[3]):
        return None
    if intent and intent.unsupported and not intent.osm_filters:
        return None
    kinds = request.interests or (intent.categories if intent else interpret(request)['interests'])
    dynamic = intent.osm_filters if intent and not request.interests else []
    # The same intent must not lose known POIs because the model picks only one synonym tag.
    # Apply the expanded filters to retrieval AND ranking, otherwise internet cafes disappear later.
    if intent and not request.interests and 'computer_club' in kinds:
        dynamic = sorted(set(dynamic) | set(TAGS['computer_club']))
        intent = intent.model_copy(update={'osm_filters': dynamic})
    if not kinds and not dynamic:
        if request.query.strip() and not (intent and (intent.general or intent.name_query)):
            return None
        kinds = list(TAGS) if intent and intent.name_query else ['park', 'attraction', 'public_space', 'cafe']
    filters = sorted(set(dynamic) if dynamic else {tag for kind in kinds for tag in TAGS.get(kind, [])})
    if not filters:
        return None
    semaphore = asyncio.Semaphore(4)
    try:
        async with asyncio.timeout(14):
            async with httpx.AsyncClient(timeout=10, headers={'Authorization': 'Bearer ' + settings.osrmroute_api_key}) as client:
                async def fetch(tag):
                    async with semaphore:
                        response = await client.get(URL, params={
                            'point': f'{request.latitude},{request.longitude}',
                            'radius': request.radius_m / 1000, 'category': tag, 'limit': 50, 'lang': 'ru',
                        })
                        if response.status_code in (401, 403):
                            # Never echo arbitrary provider messages, URLs or credentials.
                            detail = str(response.json().get('error', '')).lower()
                            message = 'OSRMRoute: подтвердите email в личном кабинете.' if 'verify your email' in detail else 'OSRMRoute: проверьте ключ и разрешение Places в личном кабинете.'
                            raise OSRMSearchError(message)
                        if response.status_code in (402, 429):
                            raise OSRMSearchError('OSRMRoute: исчерпан лимит или недостаточно кредитов.')
                        response.raise_for_status()
                        items = response.json().get('places')
                        if not isinstance(items, list):
                            raise ValueError('Invalid places response')
                        return items
                tasks = [asyncio.create_task(fetch(tag)) for tag in filters]
                try:
                    batches = await asyncio.gather(*tasks)
                finally:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
        places = MemoryPlaces(normalize_places([item for batch in batches for item in batch], intent))
        places.mode = 'live_osrmroute'
        result = recommend(request, places, places, intent)
        result.update(mode='live', data_mode='live', place_provider='OSRMRoute',
                      checked_at=datetime.now(timezone.utc).isoformat(), live_objects_count=len(places.pois))
        result['warnings'].append('OSRMRoute использует OpenStreetMap. Покрытие заведений может быть неполным; часы работы и доступность не подтверждены, если источник их не передал.')
        if result['empty_reason']:
            if places.pois:
                result['empty_reason'] = f'Источник вернул объектов: {len(places.pois)}, но они не прошли условия времени, типа или удобств. Попробуйте увеличить время или изменить фильтры.'
            else:
                result['empty_reason'] = f'OSRMRoute не вернул таких объектов в радиусе {request.radius_m / 1000:g} км. Можно увеличить радиус; база OpenStreetMap также может быть неполной.'
        return result
    except OSRMSearchError:
        raise
    except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError):
        raise OSRMSearchError('OSRMRoute не ответил вовремя или вернул ошибку. Повторите поиск позже.') from None
