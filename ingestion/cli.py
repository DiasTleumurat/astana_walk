"""Reproducible OSM ingestion. Run: python -m ingestion.cli refresh."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import time

import httpx

from backend.config import BBOX, CATEGORIES, ROOT

ENDPOINTS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
RAW_PATH = ROOT / 'data/raw/osm.json'
DATA_PATH = ROOT / 'data/poi.json'
QUERY = f'''[out:json][timeout:90];(
 nwr["leisure"~"^(park|garden|playground)$"]({','.join(map(str, BBOX))});
 nwr["tourism"~"^(museum|gallery|attraction|viewpoint)$"]({','.join(map(str, BBOX))});
 nwr["amenity"="cafe"]({','.join(map(str, BBOX))});
 nwr["amenity"~"^(internet_cafe|gaming_centre|lan_gaming_centre|restaurant|cinema|library)$"]({','.join(map(str, BBOX))});
 nwr["shop"="mall"]({','.join(map(str, BBOX))});
 nwr["leisure"~"^(fitness_centre|sports_centre)$"]({','.join(map(str, BBOX))});
 nwr["place"="square"]({','.join(map(str, BBOX))});
);out center meta;'''


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def collect(path=RAW_PATH):
    errors = []
    for endpoint in ENDPOINTS:
        for attempt in range(2):
            try:
                with httpx.Client(timeout=115, headers={'User-Agent': 'AstanaWalk-Hackathon/0.1 (POI collection)'}) as client:
                    response = client.post(endpoint, data={'data': QUERY})
                    response.raise_for_status()
                    raw = response.json()
                if 'remark' in raw or not raw.get('elements'):
                    raise ValueError('Overpass returned partial or empty data')
                raw['_collected_at'] = datetime.now(timezone.utc).isoformat()
                raw['_endpoint'] = endpoint
                raw['_query'] = QUERY
                atomic_json(path, raw)
                return raw
            except (httpx.HTTPError, ValueError) as exc:
                errors.append(type(exc).__name__)
                time.sleep(2 ** attempt)
    raise RuntimeError('Collection failed; previous snapshot was retained. ' + ', '.join(errors))


def category(tags):
    if re.search(r'компьютерн\w*\s+клуб|кибер\s*клуб|colizeum|cyber\s*x|cyber\s*arena',
                 ' '.join(str(tags.get(k, '')) for k in ('name', 'name:ru', 'name:en', 'brand')), re.I):
        return 'computer_club'
    if tags.get('amenity') in ('internet_cafe', 'gaming_centre', 'lan_gaming_centre') or tags.get('leisure') == 'gaming_centre':
        return 'computer_club'
    if tags.get('amenity') in ('fast_food', 'food_court'):
        return 'restaurant'
    if tags.get('amenity') in ('restaurant', 'cinema', 'library'):
        return tags['amenity']
    if tags.get('shop') == 'mall':
        return 'shopping_mall'
    if tags.get('leisure') in ('fitness_centre', 'sports_centre'):
        return 'fitness'
    if tags.get('leisure') in ('park', 'garden'):
        return 'park'
    if tags.get('leisure') == 'playground':
        return 'playground'
    if tags.get('amenity') == 'cafe':
        return 'cafe'
    if tags.get('tourism') in CATEGORIES:
        return tags['tourism']
    if tags.get('place') == 'square':
        return 'public_space'
    return None


def normalize(raw, allow_generic=False):
    pois, rejected, seen = [], Counter(), set()
    collected = raw.get('_collected_at', datetime.now(timezone.utc).isoformat())
    for element in raw['elements']:
        tags = element.get('tags', {})
        kind = category(tags)
        if not kind and allow_generic:
            kind = element.get('_place_kind')
        label = CATEGORIES.get(kind, element.get('_place_label', 'Место'))
        point = element if 'lat' in element else element.get('center', {})
        lat, lon = point.get('lat'), point.get('lon')
        identifier = f"osm:{element['type']}:{element['id']}"
        if identifier in seen:
            rejected['duplicate_source_id'] += 1
            continue
        if not kind or lat is None or lon is None or not (BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3]):
            rejected['unsupported_or_outside'] += 1
            continue
        if tags.get('access') in ('private', 'no') or tags.get('disused') == 'yes':
            rejected['not_public'] += 1
            continue
        # Anonymous playgrounds and parks are useful, but the label is transparent.
        name = tags.get('name:ru') or tags.get('name') or tags.get('name:en') or tags.get('name:kk')
        if not name and kind not in ('playground', 'park', 'public_space') and not allow_generic:
            rejected['missing_name'] += 1
            continue
        seen.add(identifier)
        address = ', '.join(filter(None, [tags.get('addr:street'), tags.get('addr:housenumber')]))
        source_id = identifier + ':tags'
        description = tags.get('description:ru') or tags.get('description')
        origin = 'source' if description else 'derived_from_tags'
        description = description or f"{label} в Астане." + (f' Адрес: {address}.' if address else '')
        flags = []
        if not name:
            flags.append('unnamed_in_source')
        if not tags.get('opening_hours'):
            flags.append('missing_opening_hours')
        if 'lat' not in element:
            flags.append('approximate_center')
        sources = [{
            'id': source_id, 'name': 'OpenStreetMap',
            'url': f"https://www.openstreetmap.org/{element['type']}/{element['id']}",
            'collected_at': collected, 'license': 'ODbL 1.0',
            'fields': tags, 'sha256': hashlib.sha256(json.dumps(tags, sort_keys=True).encode()).hexdigest(),
        }]
        pois.append({
            'id': identifier, 'name': name or f'{label} без названия в OSM',
            'category_label': label,
            'names': {k: v for k, v in tags.items() if k.startswith('name')},
            'latitude': lat, 'longitude': lon, 'coordinate_accuracy': 'point' if 'lat' in element else 'center',
            'categories': [kind], 'tags': tags, 'description': description[:1500], 'description_origin': origin,
            'address': address or None, 'opening_hours_raw': tags.get('opening_hours'), 'timezone': 'Asia/Almaty',
            'website': tags.get('website') or tags.get('contact:website'),
            'phone': tags.get('phone') or tags.get('contact:phone'),
            'wheelchair': {'yes': True, 'no': False}.get(tags.get('wheelchair')),
            'indoor': {'yes': True, 'no': False}.get(tags.get('indoor')),
            'child_friendly': True if kind == 'playground' else None,
            'sockets': {'yes': True, 'no': False}.get(tags.get('socket')),
            'price_level': None, 'rating': None, 'rating_source': None, 'rating_scale': None,
            'sources': sources, 'collected_at': collected, 'source_updated_at': element.get('timestamp'),
            'data_quality_flags': flags,
        })
    pois.sort(key=lambda p: p['id'])
    version = hashlib.sha256(json.dumps(pois, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    return {'version': version, 'collected_at': collected, 'bbox': BBOX, 'license': 'ODbL 1.0',
            'attribution': '© OpenStreetMap contributors', 'source_endpoint': raw.get('_endpoint'),
            'source_query': raw.get('_query', QUERY), 'rejected': dict(rejected), 'pois': pois}


def validate(data):
    pois = data['pois']
    assert pois, 'Empty dataset'
    assert len({p['id'] for p in pois}) == len(pois), 'Duplicate IDs'
    for poi in pois:
        assert poi['sources'] and poi['name'] and poi['description']
        assert BBOX[0] <= poi['latitude'] <= BBOX[2]
        assert BBOX[1] <= poi['longitude'] <= BBOX[3]
    return {'count': len(pois), 'categories': dict(Counter(p['categories'][0] for p in pois)),
            'with_hours': sum(bool(p['opening_hours_raw']) for p in pois),
            'with_wheelchair': sum(p['wheelchair'] is not None for p in pois), 'rejected': data['rejected']}


def publish(data, path=DATA_PATH):
    validate(data)
    old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'pois': []}
    previous = {p['id']: p for p in old['pois']}
    current = {p['id']: p for p in data['pois']}
    report = {'added': len(current.keys() - previous.keys()), 'removed': len(previous.keys() - current.keys()),
              'changed': sum(current[k]['sources'][0]['sha256'] != previous[k]['sources'][0]['sha256'] for k in current.keys() & previous.keys())}
    atomic_json(path, data)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['collect', 'normalize', 'validate', 'index', 'refresh', 'stats'])
    parser.add_argument('--lexical-only', action='store_true')
    args = parser.parse_args()
    if args.command == 'collect':
        print({'collected': len(collect()['elements'])})
        return
    if args.command in ('normalize', 'refresh'):
        raw = collect() if args.command == 'refresh' else json.loads(RAW_PATH.read_text(encoding='utf-8'))
        data = normalize(raw)
        if args.command == 'refresh':
            from backend.storage import Store
            from backend.search import Search
            staged = ROOT / 'data/raw/staged.json'
            validate(data)
            atomic_json(staged, data)
            staged_store = Store(staged)
            Search(staged_store, semantic=not args.lexical_only, allow_download=True)
        print(publish(data))
        print(validate(data))
    if args.command in ('validate', 'stats'):
        print(validate(json.loads(DATA_PATH.read_text(encoding='utf-8'))))
    if args.command == 'index':
        from backend.storage import Store
        from backend.search import Search
        store = Store()
        search = Search(store, semantic=not args.lexical_only, allow_download=True)
        print({'index': search.mode, 'version': store.version})


if __name__ == '__main__':
    main()
