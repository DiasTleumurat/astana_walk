import json
from pathlib import Path
import sqlite3

from backend.config import settings


def document(poi):
    from backend.config import CATEGORIES
    return ' '.join([poi['name'], *poi.get('names', {}).values(), poi['description'],
                     *[CATEGORIES.get(c, poi.get('category_label', c)) for c in poi['categories']], poi.get('address') or '',
                     ' '.join(f'{k}: {v}' for k, v in poi.get('tags', {}).items()
                              if k in ('cuisine', 'wheelchair', 'outdoor_seating', 'socket', 'opening_hours'))])


class Store:
    def __init__(self, path: Path | None = None, runtime: Path | None = None):
        self.data = json.loads((path or settings.data_path).read_text(encoding='utf-8'))
        self.pois = self.data['pois']
        self.by_id = {p['id']: p for p in self.pois}
        self.version = self.data['version']
        self.runtime = runtime or settings.runtime_dir
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.db_path = self.runtime / f'{self.version}.sqlite'
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS poi (id TEXT PRIMARY KEY, lat REAL, lon REAL, body TEXT)')
            conn.execute('CREATE VIRTUAL TABLE IF NOT EXISTS documents USING fts5(id UNINDEXED, text, tokenize="unicode61")')
            if conn.execute('SELECT count(*) FROM poi').fetchone()[0] != len(self.pois):
                conn.execute('DELETE FROM poi')
                conn.execute('DELETE FROM documents')
                conn.executemany('INSERT INTO poi VALUES (?, ?, ?, ?)', [(p['id'], p['latitude'], p['longitude'], json.dumps(p, ensure_ascii=False)) for p in self.pois])
                conn.executemany('INSERT INTO documents VALUES (?, ?)', [(p['id'], document(p)) for p in self.pois])

    def lexical(self, query, allowed: set[str]):
        import re
        tokens = re.findall(r'\w{2,}', query.lower())[:30]
        if not tokens:
            return []
        expression = ' OR '.join('"' + token + '"*' for token in tokens)
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute('SELECT id FROM documents WHERE documents MATCH ? ORDER BY bm25(documents)', (expression,)).fetchall()
        return [row[0] for row in rows if row[0] in allowed][:30]
