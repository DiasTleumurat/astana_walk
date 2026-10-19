import httpx
import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.intent import Intent
from backend.live_places import ENDPOINTS, LiveSearchError, build_query, find_live
from backend.main import app, _buckets
from backend.models import RecommendationRequest


def request(**kwargs):
    return RecommendationRequest(query='Кофе', latitude=51.1062, longitude=71.4166, **kwargs)


def intent(kind='cafe'):
    return Intent(categories=[kind], excluded=[], name_query='', unsupported='', general=False)


def test_query_uses_city_not_precise_location():
    query = build_query(request(), intent())
    assert '51.1062' not in query and '71.4166' not in query
    assert '["amenity"="cafe"]' in query
    assert 'colizeum' in build_query(request(), intent('computer_club'))


async def test_fresh_places_not_from_snapshot(monkeypatch):
    async def respond(self, url, **kwargs):
        return httpx.Response(200, request=httpx.Request('POST', url), json={
            'elements': [{'type': 'node', 'id': 987654321, 'lat': 51.1063, 'lon': 71.4167,
                          'tags': {'name': 'Fresh cafe', 'amenity': 'cafe'}}]})
    monkeypatch.setattr(httpx.AsyncClient, 'post', respond)
    result = await find_live(request(), intent())
    assert result['data_mode'] == 'live' and result['retrieval_mode'] == 'live_osm'
    assert result['checked_at']
    assert [p['name'] for p in result['recommendations']] == ['Fresh cafe']
    assert result['recommendations'][0]['sources'][0]['url'].endswith('/node/987654321')


async def test_live_empty_does_not_substitute_catalog(monkeypatch):
    async def respond(self, url, **kwargs):
        return httpx.Response(200, request=httpx.Request('POST', url), json={'elements': []})
    monkeypatch.setattr(httpx.AsyncClient, 'post', respond)
    result = await find_live(request(), intent())
    assert result['data_mode'] == 'live'
    assert not result['recommendations']
    assert 'Онлайн-поиск' in result['empty_reason']


async def test_partial_response_uses_second_provider(monkeypatch):
    calls = []
    async def respond(self, url, **kwargs):
        calls.append(url)
        data = {'elements': [], 'remark': 'timeout'} if len(calls) == 1 else {'elements': []}
        return httpx.Response(200, request=httpx.Request('POST', url), json=data)
    monkeypatch.setattr(httpx.AsyncClient, 'post', respond)
    assert (await find_live(request(), intent()))['data_mode'] == 'live'
    assert calls == list(ENDPOINTS)


async def test_total_failure_is_not_marked_live(monkeypatch):
    async def fail(*args, **kwargs):
        raise httpx.ReadTimeout('timeout')
    monkeypatch.setattr(httpx.AsyncClient, 'post', fail)
    with pytest.raises(LiveSearchError):
        await find_live(request(), intent())


def test_api_outage_is_explicit_snapshot_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'semantic_search', False)
    monkeypatch.setattr(settings, 'runtime_dir', tmp_path)
    monkeypatch.setattr(settings, 'live_place_search', True)
    async def fail(*args, **kwargs):
        raise LiveSearchError()
    monkeypatch.setattr('backend.main.find_live', fail)
    _buckets.clear()
    with TestClient(app) as client:
        result = client.post('/api/recommendations', json=request().model_dump(mode='json')).json()
    assert result['data_mode'] == 'snapshot'
    assert any('Онлайн-источник сейчас недоступен' in w for w in result['warnings'])


async def test_outside_area_does_not_contact_provider(monkeypatch):
    async def unexpected(*args, **kwargs):
        pytest.fail('No external call for unsupported location')
    monkeypatch.setattr(httpx.AsyncClient, 'post', unexpected)
    req = RecommendationRequest(query='Кофе', latitude=43.2, longitude=76.9)
    assert await find_live(req, intent()) is None
