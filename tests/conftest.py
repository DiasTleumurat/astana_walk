import copy
import json
from datetime import datetime, timezone

import pytest

from backend.storage import Store
from backend.search import Search


@pytest.fixture
def tiny_store(tmp_path):
    from ingestion.cli import normalize
    raw = {'_collected_at': datetime.now(timezone.utc).isoformat(), 'elements': [
        {'type': 'node', 'id': 1, 'lat': 51.1062, 'lon': 71.4166, 'tags': {'name': 'Test park', 'leisure': 'park', 'opening_hours': '24/7', 'wheelchair': 'yes'}},
        {'type': 'node', 'id': 2, 'lat': 51.1063, 'lon': 71.4167, 'tags': {'name': 'Test cafe', 'amenity': 'cafe'}},
        {'type': 'node', 'id': 3, 'lat': 51.1064, 'lon': 71.4168, 'tags': {'name': 'Closed museum', 'tourism': 'museum', 'opening_hours': '10:00-11:00'}},
        {'type': 'node', 'id': 4, 'lat': 51.1065, 'lon': 71.4169, 'tags': {'name': 'Playground', 'leisure': 'playground'}},
        {'type': 'node', 'id': 5, 'lat': 51.22, 'lon': 71.58, 'tags': {'name': 'Far park', 'leisure': 'park'}},
    ]}
    data = normalize(raw)
    path = tmp_path / 'poi.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return Store(path, tmp_path / 'runtime')


@pytest.fixture
def search(tiny_store):
    return Search(tiny_store, semantic=False)
