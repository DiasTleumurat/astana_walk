import copy
import json

import httpx
import pytest

from backend.config import settings
from backend.intent import Intent, resolve_intent
from backend.models import RecommendationRequest
from backend.recommend import recommend
from ingestion.cli import category


def request(query='', **kwargs):
    return RecommendationRequest(query=query, latitude=51.1062, longitude=71.4166, **kwargs)


@pytest.mark.parametrize('query,kind', [
    ('Хочу кофе', 'cafe'), ('Найди музей', 'museum'),
    ('Нужен комп. клуб', 'computer_club'), ('Компьютерный клуб', 'computer_club'),
    ('Хочу поиграть в Dota', 'computer_club'), ('Пойдем в кино', 'cinema'),
    ('Где поужинать', 'restaurant'), ('Найди библиотеку', 'library'),
    ('Нужен спортзал', 'fitness'), ('Ближайший ТРЦ', 'shopping_mall'),
])
def test_text_category_never_returns_other_types(tiny_store, search, query, kind):
    result = recommend(request(query), tiny_store, search)
    assert all(p['category'] == kind for p in result['recommendations'])
    if kind not in ('cafe', 'museum'):
        assert not result['recommendations']


def test_unknown_request_does_not_fall_back_to_nearest(tiny_store, search):
    result = recommend(request('Где ближайшая аптека'), tiny_store, search)
    assert not result['recommendations']
    assert result['empty_reason']


def test_explicit_exclusions(tiny_store, search):
    result = recommend(request('Парк без кафе'), tiny_store, search)
    assert result['recommendations']
    assert all(p['category'] == 'park' for p in result['recommendations'])


def test_exact_name_does_not_return_other_places(tiny_store, search):
    intent = Intent(categories=['cafe'], excluded=[], name_query='Test cafe', unsupported='', general=False)
    result = recommend(request('Найди Test cafe'), tiny_store, search, intent)
    assert [p['name'] for p in result['recommendations']] == ['Test cafe']
    intent.name_query = 'Does not exist'
    assert not recommend(request('Найди Does not exist'), tiny_store, search, intent)['recommendations']


def test_cuisine_is_required_not_merely_ranked(tiny_store, search):
    intent = Intent(categories=['cafe'], excluded=[], name_query='', unsupported='', general=False, cuisines=['sushi'])
    assert not recommend(request('Хочу суши'), tiny_store, search, intent)['recommendations']
    tiny_store.pois[1]['tags']['cuisine'] = 'japanese;sushi'
    result = recommend(request('Хочу суши'), tiny_store, search, intent)
    assert [p['name'] for p in result['recommendations']] == ['Test cafe']


def test_limit_not_hardcoded_to_three(tiny_store, search):
    for index in range(8):
        item = copy.deepcopy(tiny_store.pois[1])
        item['id'] = f'additional-cafe-{index}'
        tiny_store.pois.append(item)
    result = recommend(request('Кофе', limit=12), tiny_store, search)
    assert len(result['recommendations']) == 9


@pytest.mark.parametrize('tags,expected', [
    ({'amenity': 'internet_cafe'}, 'computer_club'),
    ({'amenity': 'gaming_centre'}, 'computer_club'),
    ({'amenity': 'restaurant'}, 'restaurant'), ({'amenity': 'cinema'}, 'cinema'),
    ({'amenity': 'library'}, 'library'), ({'shop': 'mall'}, 'shopping_mall'),
    ({'leisure': 'fitness_centre'}, 'fitness'),
])
def test_additional_osm_categories(tags, expected):
    assert category(tags) == expected


async def test_intent_api_validates_and_sends_no_coordinates(monkeypatch):
    monkeypatch.setattr(settings, 'llm_provider', 'gemini')
    monkeypatch.setattr(settings, 'gemini_api_key', 'test-key')
    async def respond(self, url, **kwargs):
        body = json.dumps(kwargs['json'])
        assert '51.1062' not in body and '71.4166' not in body
        assert 'test-key' not in url
        intent = {'categories': ['computer_club'], 'excluded': [], 'name_query': '', 'unsupported': '', 'general': False}
        return httpx.Response(200, request=httpx.Request('POST', url), json={'candidates': [{'content': {'parts': [{'text': json.dumps(intent)}]}}]})
    monkeypatch.setattr(httpx.AsyncClient, 'post', respond)
    assert (await resolve_intent(request('Комп клуб'))).categories == ['computer_club']


async def test_intent_network_failure_keeps_strict_local_filter(monkeypatch, tiny_store, search):
    monkeypatch.setattr(settings, 'llm_provider', 'gemini')
    monkeypatch.setattr(settings, 'gemini_api_key', 'test-key')
    async def fail(*args, **kwargs):
        raise httpx.ReadTimeout('timeout')
    monkeypatch.setattr(httpx.AsyncClient, 'post', fail)
    req = request('Нужен комп клуб')
    intent = await resolve_intent(req)
    assert intent is None
    assert not recommend(req, tiny_store, search, intent)['recommendations']
