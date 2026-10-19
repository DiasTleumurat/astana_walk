import json
import pytest
from ingestion.cli import normalize, publish, validate


def raw(elements):
    return {'elements': elements, '_collected_at': '2026-10-19T00:00:00+00:00'}


def node(identifier=1, **tags):
    return {'id': identifier, 'type': 'node', 'lat': 51.1, 'lon': 71.4, 'tags': {'leisure': 'park', 'name': 'Park', **tags}}


def test_duplicate_ids_not_names():
    dataset = normalize(raw([node(), node(), node(2)]))
    assert len(dataset['pois']) == 2
    assert dataset['rejected']['duplicate_source_id'] == 1


def test_private_places_rejected_and_unknown_preserved():
    dataset = normalize(raw([node(), node(2, access='private')]))
    assert len(dataset['pois']) == 1
    assert dataset['pois'][0]['wheelchair'] is None
    assert dataset['pois'][0]['opening_hours_raw'] is None


def test_refresh_idempotent_and_invalid_snapshot_retained(tmp_path):
    path = tmp_path / 'snapshot.json'
    dataset = normalize(raw([node()]))
    assert publish(dataset, path)['added'] == 1
    assert publish(dataset, path) == {'added': 0, 'removed': 0, 'changed': 0}
    before = path.read_bytes()
    with pytest.raises(AssertionError):
        publish(normalize(raw([])), path)
    assert path.read_bytes() == before


def test_fts_unicode_and_safe_query(tiny_store):
    ids = set(tiny_store.by_id)
    assert 'osm:node:1' in tiny_store.lexical('park', ids)
    assert isinstance(tiny_store.lexical('" OR *; DROP TABLE poi; --', ids), list)
    assert len(tiny_store.by_id) == 5
