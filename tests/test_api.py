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
        response = client.post('/api/recommendations', json={'query': 'Прогулка personal-test-marker', 'latitude': 51.1061652, 'longitude': 71.4165705})
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


def limited_after(client, headers, n=30):
    for _ in range(n):
        assert client.post('/api/recommendations', json={'latitude': 0, 'longitude': 0}, headers=headers).status_code == 200
    return client.post('/api/recommendations', json={'latitude': 0, 'longitude': 0}, headers=headers).status_code


def test_rate_limit_per_forwarded_client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'semantic_search', False)
    monkeypatch.setattr(settings, 'runtime_dir', tmp_path)
    monkeypatch.setattr(settings, 'trusted_proxy_hops', 1)
    _buckets.clear()
    with TestClient(app) as client:
        assert limited_after(client, {'X-Forwarded-For': '203.0.113.1'}) == 429
        # Another client behind the same proxy is unaffected.
        assert limited_after(client, {'X-Forwarded-For': '203.0.113.2'}, 0) == 200
        # A spoofed left-most entry is ignored: the proxy-appended address counts.
        assert limited_after(client, {'X-Forwarded-For': '198.51.100.9, 203.0.113.1'}, 0) == 429
    _buckets.clear()


def test_forwarded_header_ignored_without_trusted_proxy(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'semantic_search', False)
    monkeypatch.setattr(settings, 'runtime_dir', tmp_path)
    _buckets.clear()
    with TestClient(app) as client:
        for i in range(30):
            assert client.post('/api/recommendations', json={'latitude': 0, 'longitude': 0}, headers={'X-Forwarded-For': f'203.0.113.{i}'}).status_code == 200
        assert client.post('/api/recommendations', json={'latitude': 0, 'longitude': 0}, headers={'X-Forwarded-For': '203.0.113.99'}).status_code == 429
    _buckets.clear()


def test_bucket_overflow_keeps_active_clients(monkeypatch, tmp_path):
    from backend import main
    monkeypatch.setattr(settings, 'semantic_search', False)
    monkeypatch.setattr(settings, 'runtime_dir', tmp_path)
    monkeypatch.setattr(settings, 'trusted_proxy_hops', 1)
    monkeypatch.setattr(main, '_MAX_BUCKETS', 3)
    _buckets.clear()
    with TestClient(app) as client:
        assert limited_after(client, {'X-Forwarded-For': '203.0.113.1'}) == 429
        for i in range(2, 5):
            limited_after(client, {'X-Forwarded-For': f'203.0.113.{i}'}, 0)
            # The busy client stays limited instead of every counter being reset.
            if i < 4:
                assert limited_after(client, {'X-Forwarded-For': '203.0.113.1'}, 0) == 429
        assert len(_buckets) == 3
    _buckets.clear()


def test_stop_on_the_way_from_catalog(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'semantic_search', False)
    monkeypatch.setattr(settings, 'runtime_dir', tmp_path)
    _buckets.clear()
    with TestClient(app) as client:
        data = client.post('/api/recommendations', json={'query': 'Погулять в парке и по пути выпить кофе', 'minutes': 120,
                                                         'latitude': 51.1282, 'longitude': 71.4304}).json()
    assert data['stop_request']['label'] == 'Кофейня'
    assert data['recommendations'][0]['category'] == 'park'
    assert data['recommendations'][0]['stop']['poi_id'].startswith('osm:')
    _buckets.clear()
