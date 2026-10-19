"""Small offline vector overview from OSM; not a routing graph."""
import json
from datetime import datetime, timezone
import httpx
from backend.config import ROOT
from ingestion.cli import atomic_json

QUERY = '''[out:json][timeout:90];(
way[highway~"^(primary|secondary|tertiary|trunk)$"](51.02,71.30,51.23,71.60);
way[waterway="river"](51.02,71.30,51.23,71.60);
way[natural="water"](51.02,71.30,51.23,71.60);
way[leisure="park"](51.02,71.30,51.23,71.60);
);out geom;'''


def main():
    raw = None
    for endpoint in ('https://overpass.private.coffee/api/interpreter', 'https://overpass-api.de/api/interpreter'):
        try:
            with httpx.Client(timeout=120, headers={'User-Agent': 'AstanaWalk-Hackathon/0.1'}) as client:
                response = client.post(endpoint, data={'data': QUERY})
                response.raise_for_status()
                raw = response.json()
            break
        except (httpx.HTTPError, ValueError):
            continue
    if raw is None:
        raise RuntimeError('Basemap collection unavailable; old file retained')
    export(raw)


def export(raw):
    if raw.get('remark') or not raw.get('elements'):
        raise RuntimeError('Incomplete basemap; old file retained')
    features = []
    for way in raw['elements']:
        coords = [[round(p['lon'], 6), round(p['lat'], 6)] for p in way.get('geometry', [])]
        if len(coords) < 2:
            continue
        tags = way.get('tags', {})
        area = coords[0] == coords[-1] and (tags.get('natural') == 'water' or tags.get('leisure') == 'park')
        kind = 'water' if tags.get('natural') == 'water' or tags.get('waterway') == 'river' else ('park' if tags.get('leisure') == 'park' else 'road')
        features.append({'type': 'Feature', 'properties': {'kind': kind, 'name': tags.get('name:ru') or tags.get('name', ''), 'osm_id': way['id']},
                         'geometry': {'type': 'Polygon' if area else 'LineString', 'coordinates': [coords] if area else coords}})
    atomic_json(ROOT / 'frontend/public/astana-map.geojson', {'type': 'FeatureCollection', 'features': features})
    atomic_json(ROOT / 'data/basemap-source.json', {'source': 'OpenStreetMap / Overpass', 'query': QUERY,
        'collected_at': datetime.now(timezone.utc).isoformat(), 'license': 'ODbL 1.0', 'features': len(features)})
    print({'features': len(features)})


if __name__ == '__main__':
    main()
