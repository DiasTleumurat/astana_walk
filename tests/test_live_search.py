import json
import httpx
import pytest

from backend.config import settings
from backend.generation import enrich
from backend.models import RecommendationRequest
from backend.recommend import recommend


@pytest.fixture
def live_request(monkeypatch):
    monkeypatch.setattr(settings, 'llm_provider', 'gemini')
    monkeypatch.setattr(settings, 'gemini_api_key', 'test-key')
    return RecommendationRequest(latitude=51.1062, longitude=71.4166, query='Кофе и архитектура')


def mock_response(monkeypatch, candidate, captured, status=200):
    async def respond(self, url, **kwargs):
        captured.append((url, kwargs))
        return httpx.Response(status, request=httpx.Request('POST', url), json={'candidates': [candidate]})
    monkeypatch.setattr(httpx.AsyncClient, 'post', respond)


async def test_free_gemini_receives_wish_not_coordinates(live_request, tiny_store, search, monkeypatch):
    monkeypatch.setattr(settings, 'gemini_google_search', False)
    captured = []
    mock_response(monkeypatch, {'content': {'parts': [{'text': 'Можно выпить кофе в Test cafe.'}]}}, captured)
    result = await enrich(recommend(live_request, tiny_store, search), live_request)
    assert result['mode'] == 'live'
    assert result['live_answer']['grounding'] == 'catalog'
    assert result['live_answer']['sources']
    url, sent = captured[0]
    payload = json.loads(sent['json']['contents'][0]['parts'][0]['text'])
    assert payload['wish'] == live_request.query
    assert 'tools' not in sent['json']
    assert 'test-key' not in url
    assert sent['headers']['x-goog-api-key'] == 'test-key'
    body = json.dumps(sent['json'])
    assert '51.1062' not in body and '71.4166' not in body


async def test_initial_catalog_does_not_consume_quota(live_request, tiny_store, search, monkeypatch):
    live_request.use_ai = False
    async def unexpected(*args, **kwargs):
        pytest.fail('Initial catalog must not call Google')
    monkeypatch.setattr(httpx.AsyncClient, 'post', unexpected)
    result = await enrich(recommend(live_request, tiny_store, search), live_request)
    assert 'live_answer' not in result


async def test_web_answer_requires_search_evidence(live_request, tiny_store, search, monkeypatch):
    monkeypatch.setattr(settings, 'gemini_google_search', True)
    mock_response(monkeypatch, {'content': {'parts': [{'text': 'Неподтверждённое событие'}]}}, [])
    result = await enrich(recommend(live_request, tiny_store, search), live_request)
    assert 'live_answer' not in result
    assert any('веб-источники' in w for w in result['warnings'])


async def test_web_cyrillic_citations_and_unsafe_url(live_request, tiny_store, search, monkeypatch):
    monkeypatch.setattr(settings, 'gemini_google_search', True)
    captured = []
    text = 'Парк открыт. Проверьте часы.'
    candidate = {
        'content': {'parts': [{'text': text}]},
        'groundingMetadata': {
            'webSearchQueries': ['парк Астана'],
            'groundingChunks': [
                {'web': {'uri': 'javascript:alert(1)', 'title': 'bad'}},
                {'web': {'uri': 'https://example.com/park', 'title': 'Парк'}},
            ],
            'groundingSupports': [{'segment': {'endIndex': len('Парк открыт.'.encode('utf-8'))}, 'groundingChunkIndices': [0, 1]}],
        },
    }
    mock_response(monkeypatch, candidate, captured)
    result = await enrich(recommend(live_request, tiny_store, search), live_request)
    answer = result['live_answer']
    assert answer['grounding'] == 'web'
    assert len(answer['sources']) == 1
    assert answer['segments'][0] == {'text': 'Парк открыт.', 'sources': [1]}
    assert ''.join(p['text'] for p in answer['segments']) == text
    assert captured[0][1]['json']['tools'] == [{'google_search': {}}]


async def test_quota_failure_preserves_places(live_request, tiny_store, search, monkeypatch):
    mock_response(monkeypatch, {}, [], status=429)
    result = await enrich(recommend(live_request, tiny_store, search), live_request)
    assert result['recommendations']
    assert 'live_answer' not in result
    assert any('Лимит' in w for w in result['warnings'])
