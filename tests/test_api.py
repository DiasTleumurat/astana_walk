from fastapi.testclient import TestClient
from backend.config import settings
from backend.main import app, _buckets


def test_api_flow_no_user_persistence(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'semantic_search', False)
    monkeypatch.setattr(settings, 'runtime_dir', tmp_path)
    _buckets.clear()
    with TestClient(app) as client:
        assert client.get('/api/health').json()['status'] == 'ok'
        assert client.get('/api/ready').json()['ready']
        snapshot = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
        response = client.post('/api/recommendations', json={'query': 'personal-test-marker', 'latitude': 51.1061652, 'longitude': 71.4165705})
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'no-store'
        assert response.json()['recommendations']
        assert snapshot == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
        assert client.get('/api/poi/does-not-exist').status_code == 404
        assert client.post('/api/recommendations', json={'latitude': 200, 'longitude': 71}).status_code == 422
        assert client.post('/api/recommendations', content='x' * 9000).status_code == 413


def test_rate_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'semantic_search', False)
    monkeypatch.setattr(settings, 'runtime_dir', tmp_path)
    _buckets.clear()
    with TestClient(app) as client:
        for _ in range(30):
            assert client.post('/api/recommendations', json={'latitude': 0, 'longitude': 0}).status_code == 200
        assert client.post('/api/recommendations', json={'latitude': 0, 'longitude': 0}).status_code == 429
    _buckets.clear()
