import copy
from datetime import datetime, timezone

import pytest

from backend.models import RecommendationRequest
from backend.recommend import SCENIC, interpret, rating_score, recommend
from backend.stops import attach_stops, split_stop, stop_spec
from backend.twogis_places import normalize_items, reviews_of


def request(**kwargs):
    return RecommendationRequest(latitude=51.1061652, longitude=71.4165705,
        starts_at=datetime.now(timezone.utc).replace(hour=10, minute=0), **kwargs)


def candidate(identifier, lat, lon, **extra):
    return {'id': identifier, 'name': identifier, 'category_label': 'Пекарня', 'latitude': lat, 'longitude': lon,
            'address': None, 'opening_hours_raw': None, 'sources': [], 'categories': ['stop'], 'tags': {}, **extra}


@pytest.mark.parametrize('query, expected', [
    ('Хочу погулять в красивом место и по пути купить берлинеры (пончики такие)',
     ('Хочу погулять в красивом место', 'купить берлинеры (пончики такие)')),
    ('парк, по дороге кофе', ('парк', 'кофе')),
    ('музей, а заодно зайти в аптеку', ('музей', 'зайти в аптеку')),
    ('по пути домой парк', None), ('просто парк', None),
])
def test_split_stop(query, expected):
    assert split_stop(query) == expected


def test_stop_spec_maps_errands_to_tags():
    spec = stop_spec('купить берлинеры (пончики такие)')
    assert spec['query'] == 'берлинеры' and 'shop:bakery' in spec['osm_filters'] and 'Пекарни' in spec['rubrics']
    assert stop_spec('кофе')['osm_filters'] == ['amenity:cafe']
    assert stop_spec('забрать посылку')['osm_filters'] == []


def test_beautiful_place_is_not_only_parks():
    assert set(interpret(request(query='Хочу погулять в красивом месте'))['interests']) == set(SCENIC)


def park_result(tiny_store, search, **kwargs):
    return recommend(request(interests=['park'], **kwargs), tiny_store, search)


def test_attach_stop_prefers_small_detour(tiny_store, search):
    result = park_result(tiny_store, search)
    park = result['recommendations'][0]
    before = park['total_minutes']
    near = candidate('near', 51.1062, 71.4166)
    far = candidate('far', 51.1150, 71.4300)
    attach_stops(result, request(), stop_spec('кофе'), [far, near])
    stop = result['recommendations'][0]['stop']
    assert stop['poi_id'] == 'near'
    assert park['total_minutes'] == before + stop['extra_minutes'] and stop['extra_minutes'] >= 10


def test_attach_stop_respects_time_and_hours(tiny_store, search):
    result = park_result(tiny_store, search, minutes=30)
    closed = candidate('closed', 51.1062, 71.4166, opening_hours_raw='Mo-Su 22:00-23:00')
    too_far = candidate('far', 51.1300, 71.4600)
    attach_stops(result, request(minutes=30), stop_spec('кофе'), [closed, too_far])
    assert not any(p.get('stop') for p in result['recommendations'])
    assert any('не укладывается' in w for w in result['warnings'])


def test_places_with_stop_go_first(tiny_store, search):
    result = recommend(request(interests=['park', 'playground'], limit=3), tiny_store, search)
    assert len(result['recommendations']) >= 2
    last = result['recommendations'][-1]
    # Only the last place has a stop right next to it within a tight budget.
    result['applied_constraints']['minutes'] = last['total_minutes'] + 15
    for place in result['recommendations'][:-1]:
        place['visit_minutes'] = place['total_minutes'] = 200
    attach_stops(result, request(), stop_spec('кофе'), [candidate('stop', last['latitude'], last['longitude'])])
    assert result['recommendations'][0]['poi_id'] == last['poi_id']


def test_no_candidates_warns(tiny_store, search):
    result = attach_stops(park_result(tiny_store, search), request(), stop_spec('берлинеры'), [])
    assert any('По пути не нашлось' in w for w in result['warnings'])


def test_rating_prior_shrinks_few_reviews():
    assert rating_score({'rating': 5.0, 'review_count': 1}) < rating_score({'rating': 4.8, 'review_count': 500})
    assert rating_score({'rating': None, 'review_count': None}) == 0


def test_twogis_reviews_are_parsed_and_validated():
    item = {'id': '70000001', 'name': 'Пекарня', 'point': {'lat': 51.12, 'lon': 71.43},
            'rubrics': [{'name': 'Пекарни', 'kind': 'primary', 'id': '1'}],
            'reviews': {'general_rating': 4.73, 'general_review_count': 312}}
    poi = normalize_items([item])['pois'][0]
    assert (poi['rating'], poi['review_count'], poi['rating_source']) == (4.7, 312, '2ГИС')
    assert poi['reviews_url'].endswith('/firm/70000001/tab/reviews')
    for bad in ({'general_rating': 7, 'general_review_count': 3}, {'general_rating': 4.5, 'general_review_count': 0},
                {'general_rating': True, 'general_review_count': 3}, 'oops'):
        assert reviews_of({'reviews': bad}) == (None, None)


def test_rating_reaches_recommendation_and_ranking(tiny_store, search):
    store = copy.deepcopy(tiny_store)
    for poi in store.pois:
        if poi['categories'][0] == 'playground':
            poi.update(rating=4.9, review_count=400, rating_source='2ГИС', reviews_url='https://2gis.kz/astana/firm/1/tab/reviews')
    result = recommend(request(interests=['park', 'playground']), store, search)
    top = result['recommendations'][0]
    assert top['category'] == 'playground' and top['rating']['value'] == 4.9 and top['rating']['count'] == 400


def test_reason_for_place_at_start(tiny_store, search):
    result = recommend(RecommendationRequest(latitude=51.1062, longitude=71.4166, interests=['park']), tiny_store, search)
    assert result['recommendations'][0]['reason'].startswith('Парк рядом с вашей точкой.')


def test_reason_time_includes_stop(tiny_store, search):
    result = park_result(tiny_store, search)
    attach_stops(result, request(), stop_spec('кофе'), [candidate('near', 51.1062, 71.4166)])
    place = result['recommendations'][0]
    assert f'Оценка с остановкой по пути: {place["total_minutes"]} мин.' in place['reason']
