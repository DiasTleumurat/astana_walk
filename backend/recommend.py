from datetime import datetime, timedelta, timezone
import math
import re
import uuid

from backend.config import BBOX, CATEGORIES, settings
from backend.hours import ZONE, visit_status

DURATIONS = {'park': 25, 'cafe': 25, 'museum': 45, 'gallery': 30, 'attraction': 20,
             'playground': 25, 'viewpoint': 15, 'public_space': 20}
ACTIVITIES = {
    'park': 'Пройдитесь в спокойном темпе и сделайте небольшую паузу на прогулке.',
    'cafe': 'Сделайте перерыв на напиток. Меню, цены и свободные места уточните на месте.',
    'museum': 'Выберите одну экспозицию, чтобы оставить время на дорогу. Программу и билеты проверьте заранее.',
    'gallery': 'Рассмотрите несколько работ и выберите ту, которая запомнится. Текущую выставку уточните заранее.',
    'attraction': 'Рассмотрите объект с общедоступной территории и найдите свой ракурс для фотографии.',
    'playground': 'Сделайте остановку для игры. Подходящее по возрасту оборудование проверьте на месте.',
    'viewpoint': 'Посмотрите на город и сделайте несколько снимков, оставаясь в доступной посетителям зоне.',
    'public_space': 'Пройдитесь по общественному пространству и сделайте короткую остановку.',
}
KEYWORDS = {'park': ('парк', 'природ', 'зелень', 'зелен', 'прогуля', 'погуля'),
    'cafe': ('кофе', 'кафе', 'кофейн'), 'museum': ('музей', 'музе', 'истори'),
    'gallery': ('галере', 'искусств'), 'attraction': ('архитект', 'турист', 'достопримеч'),
    'playground': ('площадк', 'ребён', 'ребен', 'детск'), 'viewpoint': ('панорам', 'смотров'),
    'public_space': ('площадь', 'набереж')}


def distance_m(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    h = math.sin((b-a)/2)**2 + math.cos(a)*math.cos(b)*math.sin(math.radians(lon2-lon1)/2)**2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))


def interpret(request):
    """A small explicit parser; unrecognized constraints are not claimed as handled."""
    text = request.query.lower().replace('ё', 'е')
    excluded = set()
    for kind, words in KEYWORDS.items():
        if any(re.search(r'(?:без|не хочу|не предлагай|кроме)\s+(?:\w+\s+){0,1}' + re.escape(w.replace('ё', 'е')), text) for w in words):
            excluded.add(kind)
    interests = set(request.interests)
    if not interests:
        interests = {kind for kind, words in KEYWORDS.items() if any(w.replace('ё', 'е') in text for w in words)} - excluded
    minute_match = re.search(r'(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?\s*мин', text)
    hour_match = re.search(r'(\d)(?:\s*[-–]\s*(\d))?\s*час', text)
    minutes = request.minutes
    if minute_match:
        minutes = min(minutes, int(minute_match[2] or minute_match[1]))
    elif hour_match:
        minutes = min(minutes, 60 * int(hour_match[2] or hour_match[1]))
    sockets = request.sockets_required or ('розет' in text and 'без розет' not in text)
    accessible = request.accessible_only or any(w in text for w in ('инвалидн', 'без ступен', 'безбарьер'))
    child = request.with_child or any(w in text for w in ('ребен', 'детск'))
    open_now = request.open_now or 'открыто сейчас' in text or 'открыты сейчас' in text
    roundtrip = request.return_to_start or 'вернуться' in text or 'туда и обратно' in text
    return {'interests': sorted(interests), 'excluded': sorted(excluded), 'minutes': minutes,
            'radius_m': request.radius_m, 'sockets_required': sockets, 'accessible_only': accessible,
            'with_child': child, 'open_now': open_now, 'return_to_start': roundtrip}


def recommend(request, store, search):
    rules = interpret(request)
    now = request.starts_at or datetime.now(timezone.utc)
    base = {'request_id': str(uuid.uuid4()), 'mode': 'demo', 'generation_mode': 'template',
            'retrieval_mode': search.mode, 'dataset_version': store.version,
            'applied_constraints': rules, 'recommendations': [], 'warnings': [],
            'empty_reason': None, 'candidates_count': 0, 'evaluated_at': now.isoformat()}
    if not (BBOX[0] <= request.latitude <= BBOX[2] and BBOX[1] <= request.longitude <= BBOX[3]):
        base['empty_reason'] = 'Эта точка за пределами поддерживаемой области Астаны. Выберите точку на карте города.'
        return base
    if search.mode != 'hybrid':
        base['warnings'].append('Семантическая модель недоступна: используется поиск по словам и категориям.')
    if any(w in request.query.lower() for w in ('тихо', 'тишин', 'тиши', 'тихое')):
        base['warnings'].append('Уровень шума в источнике не подтверждён. Тишину в месте гарантировать нельзя.')
    if any(w in request.query.lower() for w in ('вылет', 'аэропорт', 'рейс')):
        base['warnings'].append('Время до аэропорта и прохождение контроля не рассчитаны. Укажите только время, доступное для прогулки.')
    if any(w in request.query.lower() for w in ('бесплат', 'бюджет', 'тенге', 'дешев')):
        base['warnings'].append('Цены в датасете не подтверждены. Стоимость посещения и покупки проверьте отдельно.')
    if any(w in request.query.lower() for w in ('выставк', 'событи', 'мероприят')):
        base['warnings'].append('Актуальной афиши в датасете нет. Программу мероприятий уточните у площадки.')
    if now.astimezone(ZONE).hour >= 22 or now.astimezone(ZONE).hour < 6:
        base['warnings'].append('Освещение и безопасность ночного пути не проверены. Оцените условия на месте.')
    eligible = []
    for poi in store.pois:
        kind = poi['categories'][0]
        if kind in rules['excluded']:
            continue
        if request.interests and kind not in request.interests:
            continue
        if rules['with_child'] and kind not in ('park', 'playground', 'museum', 'gallery', 'public_space'):
            continue
        if rules['accessible_only'] and poi.get('wheelchair') is not True:
            continue
        if rules['sockets_required'] and poi.get('sockets') is not True:
            continue
        distance = distance_m(request.latitude, request.longitude, poi['latitude'], poi['longitude'])
        if distance > rules['radius_m']:
            continue
        walking = max(1, math.ceil(distance / 1000 / settings.walk_speed_kmh * 60 * settings.walk_detour_factor))
        visit = DURATIONS[kind]
        total = walking * (2 if rules['return_to_start'] else 1) + visit
        if total > rules['minutes']:
            continue
        status = visit_status(poi.get('opening_hours_raw'), now + timedelta(minutes=walking), visit)
        age = (now - datetime.fromisoformat(poi['collected_at'])).total_seconds() / 86400
        if age > 180:
            status = 'unknown'
        if status == 'closed' or (rules['open_now'] and status != 'open'):
            continue
        eligible.append((poi, distance, walking, visit, total, status))
    base['candidates_count'] = len(eligible)
    query = request.query or ' '.join(CATEGORIES[x] for x in rules['interests']) or 'Прогулка по интересным местам Астаны'
    scores = search.rank(query, {p[0]['id'] for p in eligible})
    def rank(item):
        poi, distance, *_ = item
        preference = 1 if poi['categories'][0] in rules['interests'] else 0
        named = 0.04 if 'unnamed_in_source' not in poi['data_quality_flags'] else 0
        return preference + scores.get(poi['id'], 0) * 15 + 0.3 * (1-distance/rules['radius_m']) + named
    eligible.sort(key=lambda item: (-rank(item), item[0]['id']))
    for poi, distance, walking, visit, total, status in eligible[:3]:
        kind = poi['categories'][0]
        warning = []
        if status == 'unknown':
            warning.append('Часы работы не подтверждены. Проверьте перед посещением.')
        if poi['coordinate_accuracy'] == 'center':
            warning.append('На карте отмечен центр объекта; вход может находиться в другом месте.')
        why = f"{CATEGORIES[kind]} в {round(distance)} м по прямой от вашей точки."
        if kind in rules['interests']:
            why += ' Соответствует выбранным интересам.'
        why += f' Оценка посещения с дорогой: {total} мин.'
        base['recommendations'].append({
            'poi_id': poi['id'], 'name': poi['name'], 'category': kind, 'category_label': CATEGORIES[kind],
            'latitude': poi['latitude'], 'longitude': poi['longitude'], 'coordinate_accuracy': poi['coordinate_accuracy'],
            'description': poi['description'], 'description_origin': poi['description_origin'], 'address': poi['address'],
            'reason': why, 'suggested_activity': ACTIVITIES[kind], 'activity_origin': 'template_idea',
            'distance_m': round(distance), 'distance_method': 'straight_line',
            'walk_minutes': walking, 'visit_minutes': visit, 'total_minutes': total,
            'time_method': 'estimate', 'opening_status': status, 'opening_hours_raw': poi['opening_hours_raw'],
            'sources': poi['sources'], 'fact_refs': [s['id'] for s in poi['sources']],
            'collected_at': poi['collected_at'], 'warnings': warning,
            'wheelchair': poi.get('wheelchair'), 'sockets': poi.get('sockets'),
        })
    if not base['recommendations']:
        base['empty_reason'] = 'Под эти условия подтверждённых мест не найдено. Попробуйте увеличить время или радиус, либо снять строгий фильтр.'
    return base
