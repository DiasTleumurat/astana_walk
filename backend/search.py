import hashlib
import json
import os
import threading

import numpy as np

from backend.config import settings
from backend.storage import document


class Search:
    def __init__(self, store, semantic=True, allow_download=False):
        self.store = store
        self.mode = 'lexical'
        self.model = None
        self.lock = threading.Lock()
        if not semantic:
            return
        try:
            from fastembed import TextEmbedding
            settings.model_cache.mkdir(parents=True, exist_ok=True)
            # Startup is offline: model installation is an explicit bootstrap step.
            if not allow_download:
                os.environ['HF_HUB_OFFLINE'] = '1'
            self.model = TextEmbedding(model_name=settings.embedding_model, cache_dir=str(settings.model_cache),
                                       threads=2, local_files_only=not allow_download)
            docs = [document(p) for p in store.pois]
            fingerprint = hashlib.sha256((settings.embedding_model + '\n'.join(docs)).encode()).hexdigest()[:16]
            index = store.runtime / f'{store.version}-{fingerprint}.npz'
            if index.exists():
                self.vectors = np.load(index, allow_pickle=False)['vectors']
            else:
                self.vectors = np.asarray(list(self.model.embed(docs, batch_size=32)), dtype=np.float32)
                temporary = index.with_suffix('.tmp.npz')
                np.savez_compressed(temporary, vectors=self.vectors)
                os.replace(temporary, index)
            self.vectors /= np.maximum(np.linalg.norm(self.vectors, axis=1, keepdims=True), 1e-10)
            (store.runtime / 'index.json').write_text(json.dumps({'dataset_version': store.version,
                'model': settings.embedding_model, 'fingerprint': fingerprint, 'dimensions': self.vectors.shape[1]}), encoding='utf-8')
            self.mode = 'hybrid'
        except Exception:
            # No exception bodies: they may expose filesystem paths or provider URLs.
            self.model = None
            if allow_download:
                raise

    def rank(self, query, allowed):
        lexical = self.store.lexical(query, allowed)
        semantic = []
        if self.model is not None and query.strip():
            with self.lock:
                vector = np.asarray(next(iter(self.model.query_embed(query))), dtype=np.float32)
            vector /= max(float(np.linalg.norm(vector)), 1e-10)
            candidates = [(i, p['id']) for i, p in enumerate(self.store.pois) if p['id'] in allowed]
            candidates.sort(key=lambda pair: float(self.vectors[pair[0]] @ vector), reverse=True)
            semantic = [identifier for _, identifier in candidates[:30]]
        scores = {}
        for results in (lexical, semantic):
            for position, identifier in enumerate(results):
                scores[identifier] = scores.get(identifier, 0) + 1 / (60 + position + 1)
        return scores
