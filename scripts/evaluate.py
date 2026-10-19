"""Offline reproducible category-level evaluation, with real multilingual embeddings."""
import json
import platform
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.storage import Store
from backend.search import Search
from backend.models import RecommendationRequest
from backend.recommend import recommend


def main():
    cases = json.loads((ROOT / 'tests/evaluation.json').read_text(encoding='utf-8'))
    store = Store()
    search = Search(store)
    rows, times, violations, relevant = [], [], [], []
    for case in cases:
        request = RecommendationRequest(**case['input'])
        start = time.perf_counter()
        result = recommend(request, store, search)
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
        places = result['recommendations']
        rules = result['applied_constraints']
        valid = all(p['poi_id'] in store.by_id and p['distance_m'] <= rules['radius_m'] and p['total_minutes'] <= rules['minutes']
            and (not rules['open_now'] or p['opening_status'] == 'open')
            and (not rules['accessible_only'] or p['wheelchair'] is True)
            and (not rules['sockets_required'] or p['sockets'] is True)
            and set(p['fact_refs']) <= {s['id'] for s in store.by_id[p['poi_id']]['sources']} for p in places)
        if not valid:
            violations.append(case['id'])
        hit = any(p['category'] in case.get('expected_categories', []) for p in places)
        if case.get('resolvable'):
            relevant.append(hit)
        expected_empty = case.get('expected_empty', False)
        passed = valid and ((not places) if expected_empty else hit)
        rows.append({'id': case['id'], 'passed': passed, 'category_hit': hit, 'places': [p['name'] for p in places], 'latency_ms': round(elapsed, 2)})
    report = {'dataset_version': store.version, 'retrieval_mode': search.mode, 'hardware': platform.platform() + ' / ' + platform.processor(),
        'case_count': len(cases), 'passed': sum(row['passed'] for row in rows), 'hard_constraint_violations': violations,
        'category_hit_at_3': sum(relevant) / len(relevant), 'resolvable_cases': len(relevant),
        'p95_ms': round(sorted(times)[max(0, __import__('math').ceil(len(times) * .95)-1)], 2),
        'median_ms': round(statistics.median(times), 2),
        'method': 'Fixed time and locations. Author-labeled acceptable POI categories, not independent human relevance scores. 20 local requests; LLM/network excluded. Category hit is a coarse proxy, not an end-to-end RAG quality score.',
        'results': rows}
    (ROOT / 'docs').mkdir(exist_ok=True)
    (ROOT / 'docs/evaluation-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'results'}, ensure_ascii=False, indent=2))
    if report['passed'] != len(cases) or violations:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
