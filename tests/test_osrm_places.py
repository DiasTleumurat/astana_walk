import httpx
import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.main import app, _buckets
from backend.models import RecommendationRequest
from backend.osrm_places import find_osrm, normalize_places, OSRMSearchError
from backend.intent import Intent
from pydantic import ValidationError


def request(**kwargs):
    return RecommendationRequest(latitude=51.1062, longitude=71.4166, interests=['cafe'], **kwargs)


async def test_live_provider_uses_header_and_real_source_ids(monkeypatch):
    monkeypatch.setattr(settings, 'osrmroute_api_key', 'test-secret')
    async def respond(self, url, **kwargs):
        assert self.headers['Authorization'] == 'Bearer test-secret'
        assert 'key' not in kwargs['params'] and 'q' not in kwargs['params']
        assert kwargs['params']['point'] == '51.1062,71.4166'
        assert kwargs['params']['radius'] == 2.5
        return httpx.Response(200, request=httpx.Request('GET', url), json={'places': [
            {'name': 'New cafe', 'category': 'amenity', 'type': 'cafe',
             'osm_id': 123, 'osm_type': 'node', 'street': 'Street', 'housenumber': '7',
             'point': {'lat': 51.1063, 'lng': 71.4167}}]})
    monkeypatch.setattr(httpx.AsyncClient, 'get', respond)
    result = await find_osrm(request(), None)
    assert result['data_mode'] == 'live' and result['place_provider'] == 'OSRMRoute'
    place = result['recommendations'][0]
    assert place['sources'][0]['url'].endswith('/node/123')
    assert place['address'] == 'Street, 7'
    assert place['opening_status'] == 'unknown'


async def test_empty_response_stays_empty(monkeypatch):
    async def respond(self, url, **kwargs):
        return httpx.Response(200, request=httpx.Request('GET', url), json={'places': []})
    monkeypatch.setattr(httpx.AsyncClient, 'get', respond)
    result = await find_osrm(request(), None)
    assert result['data_mode'] == 'live' and not result['recommendations']
    assert 'OSRMRoute' in result['empty_reason']


@pytest.mark.parametrize('status,message', [(403, 'подтвердите email'), (402, 'кредитов'), (429, 'кредитов'), (500, 'ошибку')])
async def test_provider_errors_are_actionable_and_sanitized(monkeypatch, status, message):
    async def respond(self, url, **kwargs):
        return httpx.Response(status, request=httpx.Request('GET', url), json={
            'error': 'Verify your email address before using free API credits. secret-key'})
    monkeypatch.setattr(httpx.AsyncClient, 'get', respond)
    with pytest.raises(OSRMSearchError) as error:
        await find_osrm(request(), None)
    assert message in str(error.value) and 'secret-key' not in str(error.value)


def test_invalid_objects_dropped_and_no_fabricated_osm_link():
    data = normalize_places([
        {'name': 'bad', 'category': 'amenity', 'type': 'cafe', 'point': {'lat': True, 'lng': 71.4}},
        {'name': 'Valid', 'category': 'amenity', 'type': 'cafe', 'point': {'lat': 51.1, 'lng': 71.4}},
        {'name': 'Far', 'category': 'amenity', 'type': 'cafe', 'point': {'lat': 43.2, 'lng': 76.9}},
    ])
    assert len(data['pois']) == 1
    assert data['pois'][0]['id'].startswith('osrmroute:')
    assert 'openstreetmap.org/node' not in data['pois'][0]['sources'][0]['url']


@pytest.mark.parametrize('tag,label', [('leisure:stadium', 'Стадион'), ('amenity:veterinary', 'Ветеринарная клиника'), ('shop:bicycle', 'Веломагазин')])
async def test_types_outside_presets_reach_api_and_survive_ranking(monkeypatch, tag, label):
    key, value = tag.split(':')
    parsed = Intent(categories=[], excluded=[], name_query='', unsupported='', general=False,
                    osm_filters=[tag], place_label=label)
    async def respond(self, url, **kwargs):
        assert kwargs['params']['category'] == tag
        return httpx.Response(200, request=httpx.Request('GET', url), json={'places': [
            {'name': 'Real object', 'category': key, 'type': value, 'osm_id': 55, 'osm_type': 'way',
             'point': {'lat': 51.1063, 'lng': 71.4167}},
            {'name': 'Unrelated cafe', 'category': 'amenity', 'type': 'cafe',
             'point': {'lat': 51.1063, 'lng': 71.4167}}]})
    monkeypatch.setattr(httpx.AsyncClient, 'get', respond)
    req = RecommendationRequest(query=label, latitude=51.1062, longitude=71.4166)
    result = await find_osrm(req, parsed)
    assert result['data_mode'] == 'live'
    assert [p['name'] for p in result['recommendations']] == ['Real object']
    assert result['recommendations'][0]['category_label'] == label
    assert result['recommendations'][0]['sources'][0]['url'].endswith('/way/55')


@pytest.mark.parametrize('tag', ['leisure:stadium];out;', 'https://evil.example', 'amenity:.*', 'leisure:stadium&key=secret'])
def test_arbitrary_type_filters_are_data_not_query_code(tag):
    with pytest.raises(ValidationError):
        Intent(categories=[], excluded=[], name_query='', unsupported='', general=False, osm_filters=[tag])


async def test_gemini_narrow_club_tag_cannot_hide_internet_cafes(monkeypatch):
    from backend.osrm_places import TAGS
    calls = []
    async def respond(self, url, **kwargs):
        tag = kwargs['params']['category']
        calls.append(tag)
        items = [{'name': 'Real internet club', 'category': 'amenity', 'type': 'internet_cafe',
                  'point': {'lat': 51.1063, 'lng': 71.4167}}] if tag == 'amenity:internet_cafe' else []
        return httpx.Response(200, request=httpx.Request('GET', url), json={'places': items})
    monkeypatch.setattr(httpx.AsyncClient, 'get', respond)
    parsed = Intent(categories=['computer_club'], excluded=[], name_query='', unsupported='', general=False,
                    osm_filters=['leisure:gaming_centre'], place_label='Компьютерный клуб')
    req = RecommendationRequest(query='Хочу в комп. клуб поблизости', latitude=51.1062, longitude=71.4166)
    result = await find_osrm(req, parsed)
    assert set(calls) == set(TAGS['computer_club'])
    assert [p['name'] for p in result['recommendations']] == ['Real internet club']
    assert parsed.osm_filters == ['leisure:gaming_centre']


@pytest.mark.parametrize('query', ['Компьютерный клуб', 'Хочу в комп. клуб поблизости', 'Найди мне компьютерные клубы рядом', 'киберклуб'])
def test_common_club_phrases_skip_model(query):
    from backend.osrm_places import local_place_intent, TAGS
    req = RecommendationRequest(query=query, latitude=51.1062, longitude=71.4166)
    parsed = local_place_intent(req)
    assert parsed and parsed.categories == ['computer_club']
    assert set(parsed.osm_filters) == set(TAGS['computer_club'])


def test_site_uses_osrm_and_outage_skips_llm_and_overpass(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'osrmroute_api_key', 'test-secret')
    monkeypatch.setattr(settings, 'live_place_search', True)
    monkeypatch.setattr(settings, 'semantic_search', False)
    monkeypatch.setattr(settings, 'runtime_dir', tmp_path)
    async def fail(*args):
        raise OSRMSearchError('OSRMRoute: проверьте ключ.')
    async def unexpected(*args):
        pytest.fail('Simple search and failed provider must not invoke Gemini or Overpass')
    monkeypatch.setattr('backend.main.find_osrm', fail)
    monkeypatch.setattr('backend.main.find_live', unexpected)
    monkeypatch.setattr('backend.main.resolve_intent', unexpected)
    monkeypatch.setattr('backend.main.enrich', unexpected)
    _buckets.clear()
    with TestClient(app) as client:
        result = client.post('/api/recommendations', json=request().model_dump()).json()
    assert result['data_mode'] == 'snapshot'
    assert any('проверьте ключ' in w for w in result['warnings'])
