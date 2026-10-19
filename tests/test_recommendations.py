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
