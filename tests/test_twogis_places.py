import httpx
import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.intent import Intent
from backend.main import app, _buckets
from backend.models import RecommendationRequest
from backend.osrm_places import local_place_intent
from backend.twogis_places import find_twogis, normalize_items, queries_for, TwoGISSearchError


def request(**kwargs):
    return RecommendationRequest(query='Компьютерный клуб', latitude=51.1083923, longitude=71.4028672, limit=12, **kwargs)


def item(identifier='123', name='Top Game'):
    return {'id': identifier, 'name': name, 'point': {'lat': 51.1085, 'lon': 71.403},
            'address_name': 'Туран, 55/5', 'rubrics': [{'id': '178', 'kind': 'primary', 'name': 'Компьютерные клубы'}]}


async def test_live_clubs_pagination_sources_no_fake_osm_attributes(monkeypatch):
    monkeypatch.setattr(settings, 'twogis_api_key', 'private-key')
    pages = []
    async def respond(self, url, **kwargs):
        params = kwargs['params']
        assert params['key'] == 'private-key' and params['point'] == '71.4028672,51.1083923'
        assert params['radius'] == 2000 and params['page_size'] == 5
        pages.append(params['page'])
        batch = [item(str(params['page'] * 10 + i), f'Club {params["page"]}-{i}') for i in range(5)]
        return httpx.Response(200, request=httpx.Request('GET', url), json={'meta': {'code': 200}, 'result': {'items': batch, 'total': 40}})
    monkeypatch.setattr(httpx.AsyncClient, 'get', respond)
    req = request(radius_m=2000, minutes=120)
    result = await find_twogis(req, local_place_intent(req))
    assert sorted(pages) == [1, 2, 3]
    assert result['data_mode'] == 'live' and result['place_provider'] == '2ГИС'
    assert len(result['recommendations']) == 12 and result['provider_total'] == 40
    place = result['recommendations'][0]
    assert place['category'] == 'computer_club' and place['opening_status'] == 'unknown'
    assert place['sources'][0]['url'].startswith('https://2gis.kz/astana/firm/')
    assert not any('интернет-кафе' in w for w in place['warnings'])
    assert 'private-key' not in str(result)


async def test_native_search_not_limited_to_osm_types(monkeypatch):
    parsed = Intent(categories=[], excluded=[], name_query='', unsupported='', general=False,
                    osm_filters=['leisure:stadium'], place_label='Стадион')
    async def respond(self, url, **kwargs):
        assert kwargs['params']['q'] == 'Стадион'
        stadium = item()
        stadium['rubrics'] = [{'id': '999', 'name': 'Стадионы'}]
        return httpx.Response(200, request=httpx.Request('GET', url), json={'meta': {'code': 200}, 'result': {'items': [stadium], 'total': 1}})
    monkeypatch.setattr(httpx.AsyncClient, 'get', respond)
    req = request()
    req.query = 'Найди стадион'
    result = await find_twogis(req, parsed)
    assert len(result['recommendations']) == 1
    assert result['recommendations'][0]['category_label'] == 'Стадионы'


@pytest.mark.parametrize('code', [401, 403, 429, 500])
async def test_errors_never_leak_provider_key(monkeypatch, code):
    async def respond(self, url, **kwargs):
        return httpx.Response(200, request=httpx.Request('GET', url + '?key=secret'), json={'meta': {'code': code, 'error': {'message': 'secret'}}})
    monkeypatch.setattr(httpx.AsyncClient, 'get', respond)
    with pytest.raises(TwoGISSearchError) as error:
        await find_twogis(request(), None)
    assert 'secret' not in str(error.value)


async def test_successful_empty_stays_live(monkeypatch):
    async def respond(self, url, **kwargs):
        return httpx.Response(200, request=httpx.Request('GET', url), json={'meta': {'code': 404}})
    monkeypatch.setattr(httpx.AsyncClient, 'get', respond)
    result = await find_twogis(request(), None)
    assert result['data_mode'] == 'live' and not result['recommendations']
    assert '2ГИС' in result['empty_reason']


def test_invalid_coordinates_and_ids_are_dropped_and_duplicates_removed():
    bad = item('not-an-id')
    bad_point = item('456')
    bad_point['point']['lat'] = True
    assert len(normalize_items([item(), item(), bad, bad_point])['pois']) == 1


def test_specific_food_and_arbitrary_queries_kept():
    req = request()
    req.query = 'Хочу суши'
    parsed = Intent(categories=['restaurant'], excluded=[], name_query='', unsupported='', general=False, cuisines=['sushi'])
    assert queries_for(req, parsed) == ['Хочу суши']
    req.query = 'Прокат велосипедов'
    assert queries_for(req, None) == ['Прокат велосипедов']


def test_configured_twogis_takes_priority_over_osrm(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'twogis_api_key', 'test-key')
    monkeypatch.setattr(settings, 'osrmroute_api_key', 'other-key')
    monkeypatch.setattr(settings, 'live_place_search', True)
    monkeypatch.setattr(settings, 'semantic_search', False)
    monkeypatch.setattr(settings, 'runtime_dir', tmp_path)
    async def fail(*args):
        raise TwoGISSearchError('2ГИС: проверьте ключ.')
    async def unexpected(*args):
        pytest.fail('Do not silently fall back to another live provider or Gemini')
    monkeypatch.setattr('backend.main.find_twogis', fail)
    monkeypatch.setattr('backend.main.find_osrm', unexpected)
    monkeypatch.setattr('backend.main.enrich', unexpected)
    _buckets.clear()
    with TestClient(app) as client:
        assert client.get('/api/dataset/status').json()['place_provider'] == '2ГИС'
        data = client.post('/api/recommendations', json=request().model_dump()).json()
    assert data['data_mode'] == 'snapshot' and any('2ГИС' in w for w in data['warnings'])
