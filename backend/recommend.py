from datetime import datetime, timedelta, timezone
import math
import re
import uuid

from backend.config import BBOX, CATEGORIES, settings
from backend.hours import ZONE, visit_status

DURATIONS = {'park': 25, 'cafe': 25, 'museum': 45, 'gallery': 30, 'attraction': 20,
             'playground': 25, 'viewpoint': 15, 'public_space': 20,
             'computer_club': 30, 'restaurant': 35, 'cinema': 90,
             'shopping_mall': 30, 'library': 25, 'fitness': 45}
ACTIVITIES = {
    'park': 'Пройдитесь в спокойном темпе и сделайте небольшую паузу на прогулке.',
    'cafe': 'Сделайте перерыв на напиток. Меню, цены и свободные места уточните на месте.',
    'museum': 'Выберите одну экспозицию, чтобы оставить время на дорогу. Программу и билеты проверьте заранее.',
    'gallery': 'Рассмотрите несколько работ и выберите ту, которая запомнится. Текущую выставку уточните заранее.',
    'attraction': 'Рассмотрите объект с общедоступной территории и найдите свой ракурс для фотографии.',
    'playground': 'Сделайте остановку для игры. Подходящее по возрасту оборудование проверьте на месте.',
    'viewpoint': 'Посмотрите на город и сделайте несколько снимков, оставаясь в доступной посетителям зоне.',
    'public_space': 'Пройдитесь по общественному пространству и сделайте короткую остановку.',
    'computer_club': 'Выберите игровую сессию. Наличие свободных компьютеров и тариф уточните у клуба.',
    'restaurant': 'Остановитесь поесть. Меню, цены и свободные столики уточните у заведения.',
    'cinema': 'Выберите сеанс. Расписание, длительность фильма и билеты уточните у кинотеатра.',
    'shopping_mall': 'Пройдитесь по торговому центру. Наличие нужных магазинов уточните заранее.',
    'library': 'Загляните в библиотеку. Правила доступа и часы работы уточните перед посещением.',
    'fitness': 'Запланируйте тренировку. Условия разового посещения и расписание уточните заранее.',
}
KEYWORDS = {'park': ('парк', 'природ', 'зелень', 'зелен', 'прогуля', 'погуля'),
    'cafe': ('кофе', 'кафе', 'кофейн'), 'museum': ('музей', 'музе', 'истори'),
    'gallery': ('галере', 'искусств'), 'attraction': ('архитект', 'турист', 'достопримеч'),
    'playground': ('детская площад', 'детскую площад', 'playground'), 'viewpoint': ('панорам', 'смотров'),
    'public_space': ('площадь', 'набереж'),
    'computer_club': ('комп клуб', 'комп. клуб', 'компьютерн', 'киберклуб', 'кибер клуб', 'киберспорт', 'cyber', 'gaming', 'cs2', 'dota', 'доту', 'контр страйк'),
    'restaurant': ('ресторан', 'поесть', 'покушать', 'пообедать', 'поужинать', 'restaurant'),
    'cinema': ('кино', 'фильм', 'cinema'), 'shopping_mall': ('торгов', 'трц', 'шопинг', 'шоппинг', 'mall'),
    'library': ('библиотек', 'library'), 'fitness': ('фитнес', 'тренажер', 'спортзал', 'бассейн', 'fitness')}
# "A beautiful place" is any scenic kind, not only parks.
SCENIC_WORDS = ('красив', 'живописн', 'атмосферн', 'фотогеничн')
SCENIC = ('park', 'viewpoint', 'attraction', 'public_space')
# Bayesian prior: a single 5.0 review must not outrank 4.8 from hundreds of visitors.
RATING_PRIOR, RATING_PRIOR_WEIGHT = 4.0, 10
# Stems that start a keyword but mean something else ("парковка" is parking).
NOT_KEYWORDS = ('парковк', 'парковоч')
HOUR_WORDS = {'один': 1, 'одного': 1, 'полтора': 1.5, 'полутора': 1.5, 'два': 2, 'двух': 2, 'три': 3, 'трех': 3}
_NUMBER = r'(\d+(?:[.,]\d+)?|' + '|'.join(HOUR_WORDS) + r')'
_HOURS = re.compile(r'(?<![\w.,])' + _NUMBER + r'(?:\s*[-–]\s*' + _NUMBER + r')?(\s+с\s+половиной)?\s*час|(?<!\w)(пол)\s*час|(?<!\w)(?:на|за|в течение)\s+(час)(?:а|ик)?(?!\w)')
_MINUTES = re.compile(r'(?<!\w)(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?\s*мин')
_NEGATION = r'(?<!\w)(?:не|без)\s+(?:(?:хочу|хотим|надо|нужно|обязательно|буду|планирую|придется)\s+)?'
_ROUNDTRIP = r'(?:вернуться|возвращ\w*)'


def keyword(word):
    """Keywords are word stems: they must start a word, so "mall" does not match "small"."""
    return r'(?<!\w)(?!' + '|'.join(NOT_KEYWORDS) + ')' + re.escape(word.replace('ё', 'е'))


def scenic(text):
    return any(re.search(keyword(w), text.lower()) for w in SCENIC_WORDS)


def rating_score(poi):
    """Rating above (or below) the prior, shrunk towards it when reviews are few."""
    rating, count = poi.get('rating'), poi.get('review_count') or 0
    if isinstance(rating, bool) or not isinstance(rating, (int, float)) or count <= 0:
        return 0
    return (RATING_PRIOR_WEIGHT * RATING_PRIOR + count * rating) / (RATING_PRIOR_WEIGHT + count) - RATING_PRIOR


def rating_of(poi):
    if poi.get('rating') is None:
        return None
    return {'value': poi['rating'], 'count': poi.get('review_count'), 'source': poi.get('rating_source'), 'url': poi.get('reviews_url')}


def hours_value(raw):
    return HOUR_WORDS.get(raw) or float(raw.replace(',', '.'))


def parse_minutes(text):
    """Return the duration limit stated in the text, or None."""
    hours = _HOURS.search(text)
    minute_match = _MINUTES.search(text)
    hour_minutes = None
    if hours:
        if hours[4]:
            hour_minutes = 30
        elif hours[5]:
            hour_minutes = 60
        else:
            hour_minutes = 60 * (hours_value(hours[2] or hours[1]) + (0.5 if hours[3] else 0))
    if hour_minutes is not None and minute_match and minute_match.start() >= hours.end() and re.fullmatch(r'\w*\s*(?:и\s+)?', text[hours.end():minute_match.start()]):
        return round(hour_minutes) + int(minute_match[2] or minute_match[1])  # "1 час 30 минут"
    if minute_match:
        return int(minute_match[2] or minute_match[1])
    return round(hour_minutes) if hour_minutes is not None else None


def distance_m(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    h = math.sin((b-a)/2)**2 + math.cos(a)*math.cos(b)*math.sin(math.radians(lon2-lon1)/2)**2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))


def interpret(request):
    """A small explicit parser; unrecognized constraints are not claimed as handled."""
    text = request.query.lower().replace('ё', 'е')
    excluded = set()
    for kind, words in KEYWORDS.items():
        if any(re.search(r'(?<!\w)(?:без|не хочу|не предлагай|кроме)\s+(?:\w+\s+){0,1}' + keyword(w), text) for w in words):
            excluded.add(kind)
    interests = set(request.interests)
    if not interests:
        interests = {kind for kind, words in KEYWORDS.items() if any(re.search(keyword(w), text) for w in words)}
        if scenic(text):
            interests |= set(SCENIC)
        interests -= excluded
    minutes = request.minutes
    stated = parse_minutes(text)
    if stated:
        minutes = min(minutes, stated)
    sockets = request.sockets_required or ('розет' in text and 'без розет' not in text)
    accessible = request.accessible_only or any(w in text for w in ('инвалидн', 'без ступен', 'безбарьер'))
    child = request.with_child or any(w in text for w in ('ребен', 'детск'))
    open_now = request.open_now or 'открыто сейчас' in text or 'открыты сейчас' in text
    roundtrip = request.return_to_start or 'туда и обратно' in text or (
        bool(re.search(r'(?<!\w)' + _ROUNDTRIP, text)) and not re.search(_NEGATION + _ROUNDTRIP, text))
    return {'interests': sorted(interests), 'excluded': sorted(excluded), 'minutes': minutes, 'time_enabled': request.time_enabled,
            'radius_m': request.radius_m, 'sockets_required': sockets, 'accessible_only': accessible,
            'with_child': child, 'open_now': open_now, 'return_to_start': roundtrip}


def recommend(request, store, search, intent=None):
    rules = interpret(request)
    if intent is not None:
        rules['excluded'] = sorted(set(rules['excluded']) | set(intent.excluded))
        if not request.interests:
            rules['interests'] = sorted(set(intent.categories) - set(rules['excluded']))
    name_query = intent.name_query.casefold().strip() if intent else ''
    osm_filters = intent.osm_filters if intent else []
    general = intent.general if intent else bool(not request.query.strip() or re.search(r'прогул|погуля|прогуля|посмотреть город|реб[её]н|дет[ьи]|посоветуй места|интересные места', request.query.lower()))
    now = request.starts_at or datetime.now(timezone.utc)
    base = {'request_id': str(uuid.uuid4()), 'mode': 'demo', 'generation_mode': 'template',
            'retrieval_mode': search.mode, 'dataset_version': store.version,
            'applied_constraints': rules, 'recommendations': [], 'warnings': [],
            'empty_reason': None, 'candidates_count': 0, 'evaluated_at': now.isoformat()}
    base['query_understanding'] = {
        'categories': ([intent.place_label] if osm_filters and intent.place_label else [CATEGORIES[k] for k in rules['interests']]),
        'name': intent.name_query if intent else '',
        'cuisines': intent.cuisines if intent else [],
        'method': intent._method if intent else 'local',
    }
    if intent is not None and intent.unsupported and not osm_filters and search.mode != 'live_2gis':
        base['empty_reason'] = 'Не удалось понять, какое место вы ищете. Укажите тип объекта или его название.'
        return base
    if not (BBOX[0] <= request.latitude <= BBOX[2] and BBOX[1] <= request.longitude <= BBOX[3]):
        base['empty_reason'] = 'Эта точка за пределами поддерживаемой области Астаны. Выберите точку на карте города.'
        return base
    if search.mode == 'lexical':
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
        provider_match = search.mode == 'live_2gis' and poi.get('provider_search_match') is True
        if kind in rules['excluded']:
            continue
        if provider_match and not request.interests:
            pass  # Native 2GIS text/rubric search already matched the request; OSM tags don't apply.
        elif osm_filters and not request.interests:
            if not any(poi.get('tags', {}).get(tag.split(':', 1)[0]) == tag.split(':', 1)[1] for tag in osm_filters):
                continue
        elif rules['interests'] and kind not in rules['interests']:
            continue
        names = [poi['name'].casefold(), *[n.casefold() for n in poi.get('names', {}).values()]]
        if name_query and not provider_match and not any(name_query in name for name in names):
            continue
        if intent is not None and intent.cuisines and not provider_match:
            cuisines = {v.strip().casefold() for v in poi.get('tags', {}).get('cuisine', '').split(';')}
            if not cuisines.intersection(c.casefold() for c in intent.cuisines):
                continue
        if not provider_match and not osm_filters and not rules['interests'] and not name_query and not general and not any(name in request.query.casefold() for name in names if len(name) >= 3):
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
        visit = DURATIONS.get(kind, 30)
        total = walking * (2 if rules['return_to_start'] else 1) + visit
        if rules['time_enabled'] and total > rules['minutes']:
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
    beautiful = scenic(request.query)
    def rank(item):
        poi, distance, *_ = item
        preference = 1 if poi['categories'][0] in rules['interests'] else 0
        # An unnamed OSM square is rarely what "a beautiful place" means.
        named = (0.6 if beautiful else 0.04) if 'unnamed_in_source' not in poi['data_quality_flags'] else 0
        return preference + scores.get(poi['id'], 0) * 15 + 0.3 * (1-distance/rules['radius_m']) + named + 0.25 * rating_score(poi)
    eligible.sort(key=lambda item: (-rank(item), item[0]['id']))
    for poi, distance, walking, visit, total, status in eligible[:request.limit]:
        kind = poi['categories'][0]
        warning = []
        if kind == 'computer_club' and poi.get('tags', {}).get('amenity') == 'internet_cafe':
            warning.append('В OpenStreetMap объект отмечен как интернет-кафе. Наличие игровых ПК и нужных игр уточните у заведения.')
        if status == 'unknown':
            warning.append('Часы работы не подтверждены. Проверьте перед посещением.')
        if poi['coordinate_accuracy'] == 'center':
            warning.append('На карте отмечен центр объекта; вход может находиться в другом месте.')
        label = CATEGORIES.get(kind, poi.get('category_label', 'Место'))
        why = f"{label} рядом с вашей точкой." if distance < 30 else f"{label} в {round(distance)} м по прямой от вашей точки."
        if kind in rules['interests']:
            why += ' Соответствует выбранным интересам.'
        why += f' Оценка посещения с дорогой: {total} мин.'
        base['recommendations'].append({
            'poi_id': poi['id'], 'name': poi['name'], 'category': kind, 'category_label': label,
            'latitude': poi['latitude'], 'longitude': poi['longitude'], 'coordinate_accuracy': poi['coordinate_accuracy'],
            'description': poi['description'], 'description_origin': poi['description_origin'], 'address': poi['address'],
            'reason': why, 'suggested_activity': ACTIVITIES.get(kind, 'Уточните часы работы и условия посещения перед выходом.'), 'activity_origin': 'template_idea',
            'distance_m': round(distance), 'distance_method': 'straight_line',
            'walk_minutes': walking, 'visit_minutes': visit, 'total_minutes': total,
            'time_method': 'estimate', 'opening_status': status, 'opening_hours_raw': poi['opening_hours_raw'],
            'sources': poi['sources'], 'fact_refs': [s['id'] for s in poi['sources']],
            'collected_at': poi['collected_at'], 'warnings': warning,
            'wheelchair': poi.get('wheelchair'), 'sockets': poi.get('sockets'),
            'rating': rating_of(poi),
        })
    if not base['recommendations']:
        base['empty_reason'] = ('Подходящих запросу мест в каталоге в выбранном радиусе и времени не найдено. Попробуйте увеличить время или радиус. Другие типы мест не подставлены.' if request.time_enabled else 'Подходящих запросу мест в выбранном радиусе с этими фильтрами не найдено. Попробуйте увеличить радиус или изменить фильтры.')
    return base
