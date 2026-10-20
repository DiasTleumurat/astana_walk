from datetime import datetime, timezone
import pytest
from backend.models import RecommendationRequest
from backend.recommend import distance_m, interpret, recommend


def request(**kwargs):
    return RecommendationRequest(latitude=51.1061652, longitude=71.4165705,
        starts_at=datetime.now(timezone.utc).replace(hour=10, minute=0), **kwargs)


def test_time_and_radius_are_hard_constraints(tiny_store, search):
    result = recommend(request(minutes=30, radius_m=500), tiny_store, search)
    assert result['recommendations']
    assert all(p['total_minutes'] <= 30 and p['distance_m'] <= 500 for p in result['recommendations'])
    assert all(p['poi_id'] != 'osm:node:5' for p in result['recommendations'])


def test_disabling_time_keeps_long_visits_but_preserves_radius(tiny_store, search):
    cinema = tiny_store.pois[1]
    cinema['categories'] = ['cinema']
    cinema['name'] = 'Test cinema'
    limited = recommend(request(query='Кинотеатр', minutes=30, radius_m=500), tiny_store, search)
    assert not limited['recommendations']
    unlimited = recommend(request(query='Кинотеатр', minutes=30, radius_m=500, time_enabled=False), tiny_store, search)
    assert len(unlimited['recommendations']) == 1
    assert unlimited['recommendations'][0]['total_minutes'] > 30
    assert unlimited['recommendations'][0]['visit_minutes'] == 90
    assert unlimited['applied_constraints']['time_enabled'] is False
    cinema['latitude'], cinema['longitude'] = 51.22, 71.58
    assert not recommend(request(query='Кинотеатр', time_enabled=False, radius_m=500), tiny_store, search)['recommendations']


def test_time_switch_overrides_time_mentioned_in_query(tiny_store, search):
    req = request(query='Кафе на 15 минут', minutes=60, interests=['cafe'], time_enabled=False)
    result = recommend(req, tiny_store, search)
    assert result['recommendations']
    assert result['recommendations'][0]['total_minutes'] > 15
    assert not recommend(req.model_copy(update={'time_enabled': True}), tiny_store, search)['recommendations']


def test_strict_filters_exclude_unknown(tiny_store, search):
    assert recommend(request(sockets_required=True), tiny_store, search)['recommendations'] == []
    result = recommend(request(accessible_only=True, open_now=True), tiny_store, search)
    assert [p['poi_id'] for p in result['recommendations']] == ['osm:node:1']


def test_unknown_hours_are_not_open(tiny_store, search):
    result = recommend(request(interests=['cafe']), tiny_store, search)
    assert result['recommendations'][0]['opening_status'] == 'unknown'
    assert not recommend(request(interests=['cafe'], open_now=True), tiny_store, search)['recommendations']


def test_roundtrip_counts_return_leg(tiny_store, search):
    one = recommend(request(interests=['park']), tiny_store, search)['recommendations'][0]
    two = recommend(request(interests=['park'], return_to_start=True), tiny_store, search)['recommendations'][0]
    assert two['total_minutes'] == one['total_minutes'] + one['walk_minutes']


def test_outside_area_returns_clear_empty(tiny_store, search):
    result = recommend(RecommendationRequest(latitude=43.2, longitude=76.9), tiny_store, search)
    assert not result['recommendations']
    assert 'пределами' in result['empty_reason']


def test_child_excludes_cafes(tiny_store, search):
    result = recommend(request(with_child=True), tiny_store, search)
    assert all(p['category'] in ('park', 'playground', 'museum', 'gallery', 'public_space') for p in result['recommendations'])


def test_plaintext_constraints():
    parsed = interpret(request(query='С ребенком, без кафе, на 30 минут, нужны розетки и вернуться'))
    assert parsed['with_child'] and parsed['sockets_required'] and parsed['return_to_start']
    assert parsed['minutes'] == 30 and 'cafe' in parsed['excluded']


def test_distance_and_invalid_inputs():
    assert distance_m(51, 71, 51, 71) == 0
    assert 111000 < distance_m(51, 71, 52, 71) < 112000
    with pytest.raises(ValueError):
        RecommendationRequest(latitude=float('nan'), longitude=71)
    with pytest.raises(ValueError):
        request(minutes=0)


def test_source_ids_match_selected_places(tiny_store, search):
    result = recommend(request(), tiny_store, search)
    for item in result['recommendations']:
        assert set(item['fact_refs']) == {s['id'] for s in tiny_store.by_id[item['poi_id']]['sources']}


def test_unsupported_opening_expression_stays_unknown(tiny_store, search):
    tiny_store.by_id['osm:node:1']['opening_hours_raw'] = 'Mo-Su sunrise-sunset'
    assert not recommend(request(open_now=True), tiny_store, search)['recommendations']


@pytest.mark.parametrize('query, minutes', [
    ('Гулять 1.5 часа', 90), ('1,5 часа', 90), ('полтора часа в парке', 90), ('на полчаса', 30),
    ('два с половиной часа', 150), ('1 час 30 минут', 90), ('на час в кафе', 60), ('1-2 часа', 120),
    ('10 часов', 180), ('30 минут, потом 2 часа', 30), ('часы работы парка', 180),
])
def test_duration_phrases(query, minutes):
    assert interpret(request(query=query, minutes=180))['minutes'] == minutes


@pytest.mark.parametrize('query, interests', [
    ('small кафе', ['cafe']), ('нужна парковка рядом', []), ('без парковки, в кафе', ['cafe']),
    ('в торговый центр', ['shopping_mall']), ('mall', ['shopping_mall']), ('парков рядом нет?', ['park']),
])
def test_keywords_match_word_starts_only(query, interests):
    parsed = interpret(request(query=query))
    assert parsed['interests'] == interests and parsed['excluded'] == []


@pytest.mark.parametrize('query, roundtrip', [
    ('Парк, затем вернуться', True), ('нужно возвращаться к старту', True), ('туда и обратно', True),
    ('не хочу возвращаться', False), ('не надо вернуться', False), ('без возвращения', False),
])
def test_return_to_start_respects_negation(query, roundtrip):
    assert interpret(request(query=query))['return_to_start'] is roundtrip
