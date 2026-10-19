from collections import Counter, defaultdict, deque
from contextlib import asynccontextmanager
import hashlib
import secrets
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from backend.config import ROOT, settings
from backend.generation import enrich
from backend.models import RecommendationRequest
from backend.recommend import recommend
from backend.search import Search
from backend.storage import Store


@asynccontextmanager
async def lifespan(app):
    app.state.store = Store()
    app.state.search = Search(app.state.store, semantic=settings.semantic_search)
    yield


app = FastAPI(title='Astana Walk', version='0.1.0', lifespan=lifespan)
_buckets = defaultdict(deque)
_salt = secrets.token_bytes(16)


@app.middleware('http')
async def limits(request: Request, call_next):
    if request.url.path.startswith('/api/'):
        length = request.headers.get('content-length', '0')
        if not length.isdigit() or int(length) > 8192:
            return JSONResponse({'detail': 'Запрос слишком большой.'}, status_code=413)
        if request.method == 'POST':
            body = b''
            async for chunk in request.stream():
                body += chunk
                if len(body) > 8192:
                    return JSONResponse({'detail': 'Запрос слишком большой.'}, status_code=413)
            request._body = body
            now = time.monotonic()
            key = hashlib.blake2b((request.client.host if request.client else 'local').encode(), key=_salt, digest_size=12).digest()
            if len(_buckets) > 2048:
                _buckets.clear()
            times = _buckets[key]
            while times and times[0] < now - 60:
                times.popleft()
            if len(times) >= 30:
                return JSONResponse({'detail': 'Слишком много запросов. Попробуйте через минуту.'}, status_code=429)
            times.append(now)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Permissions-Policy'] = 'geolocation=(self)'
    response.headers['Cache-Control'] = 'no-store' if request.url.path.startswith('/api/') else 'no-cache'
    return response


@app.get('/api/health')
def health():
    return {'status': 'ok'}


@app.get('/api/ready')
def ready():
    return {'ready': bool(app.state.store.pois), 'retrieval_mode': app.state.search.mode,
            'llm_configured': settings.llm_provider == 'gemini' and bool(settings.gemini_api_key)}


@app.get('/api/dataset/status')
def dataset_status():
    store = app.state.store
    return {'version': store.version, 'count': len(store.pois), 'collected_at': store.data['collected_at'],
            'categories': dict(Counter(p['categories'][0] for p in store.pois)),
            'attribution': store.data['attribution'], 'license': store.data['license'],
            'retrieval_mode': app.state.search.mode, 'model': settings.embedding_model if app.state.search.mode == 'hybrid' else None}


@app.get('/api/poi/{identifier:path}')
def poi(identifier: str):
    if identifier not in app.state.store.by_id:
        raise HTTPException(404, 'Место не найдено')
    return app.state.store.by_id[identifier]


@app.post('/api/recommendations')
async def recommendations(request: RecommendationRequest):
    result = await run_in_threadpool(recommend, request, app.state.store, app.state.search)
    return await enrich(result, request)


if (ROOT / 'frontend/dist').exists():
    app.mount('/', StaticFiles(directory=ROOT / 'frontend/dist', html=True), name='web')
