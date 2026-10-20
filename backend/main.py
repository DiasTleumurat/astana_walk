from collections import Counter, OrderedDict, deque
from contextlib import asynccontextmanager
import asyncio
import hashlib
import ipaddress
import secrets
import time
import re

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from backend.config import ROOT, settings
from backend.generation import enrich
from backend.intent import resolve_intent
from backend.live_places import find_live, LiveSearchError
from backend.osrm_places import find_osrm, OSRMSearchError, local_place_intent
from backend.twogis_places import find_twogis, TwoGISSearchError
from backend.models import RecommendationRequest
from backend.recommend import recommend
from backend.search import Search
from backend.stops import attach_stops, split_stop, stop_candidates
from backend.storage import Store


@asynccontextmanager
async def lifespan(app):
    app.state.store = Store()
    app.state.search = Search(app.state.store, semantic=settings.semantic_search)
    yield


app = FastAPI(title='Astana Walk', version='0.1.0', lifespan=lifespan)
_buckets = OrderedDict()
_MAX_BUCKETS = 2048
_salt = secrets.token_bytes(16)


def client_address(request: Request):
    peer = request.client.host if request.client else 'local'
    hops = settings.trusted_proxy_hops
    if hops <= 0:
        return peer
    chain = [part.strip() for header in request.headers.getlist('x-forwarded-for') for part in header.split(',')]
    # Each trusted proxy appends the address it saw; entries further left are client-supplied.
    if len(chain) < hops:
        return peer
    try:
        return str(ipaddress.ip_address(chain[-hops]))
    except ValueError:
        return peer


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
            key = hashlib.blake2b(client_address(request).encode(), key=_salt, digest_size=12).digest()
            times = _buckets.setdefault(key, deque())
            _buckets.move_to_end(key)
            # Evict the least recently seen clients, never the active ones' history.
            while len(_buckets) > _MAX_BUCKETS:
                _buckets.popitem(last=False)
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
            'retrieval_mode': app.state.search.mode, 'model': settings.embedding_model if app.state.search.mode == 'hybrid' else None,
            'ai_configured': settings.llm_provider == 'gemini' and bool(settings.gemini_api_key),
            'web_search_enabled': settings.gemini_google_search,
            'live_place_search': settings.live_place_search,
            'place_provider': '2ГИС' if settings.twogis_api_key else ('OSRMRoute' if settings.osrmroute_api_key else 'OpenStreetMap')}


@app.get('/api/poi/{identifier:path}')
def poi(identifier: str):
    if identifier not in app.state.store.by_id:
        raise HTTPException(404, 'Место не найдено')
    return app.state.store.by_id[identifier]


@app.post('/api/recommendations')
async def recommendations(request: RecommendationRequest):
    # "Погулять в парке и по пути купить кофе": search the destination, then the stop.
    split = split_stop(request.query)
    wish = request.model_copy(update={'query': split[0]}) if split else request
    stop_search = asyncio.create_task(stop_candidates(request, split[1], app.state.store)) if split else None
    async def with_stop(result):
        return attach_stops(result, request, *await stop_search) if stop_search else result
    simple = re.fullmatch(r'\s*(?:(?:хочу|найди|найдите)(?: мне)?\s+)?(?:в\s+)?(?:компьютерн\w* клуб\w*|комп\.? клуб\w*|кофе|кафе|парк\w*|кинотеатр\w*|музе\w*)[.!?\s]*', wish.query, re.I)
    keyed_search = bool(settings.twogis_api_key or settings.osrmroute_api_key)
    local_intent = local_place_intent(wish) if wish.use_ai and keyed_search else None
    intent = local_intent or (None if keyed_search and (simple or (wish.interests and not wish.query.strip())) else await resolve_intent(wish))
    live_failed = False
    provider_error = None
    if wish.use_ai and settings.live_place_search:
        try:
            live = await (find_twogis(wish, intent) if settings.twogis_api_key else (find_osrm(wish, intent) if settings.osrmroute_api_key else find_live(wish, intent)))
            if live is not None:
                return await with_stop(live)
        except LiveSearchError as error:
            live_failed = True
            if isinstance(error, (OSRMSearchError, TwoGISSearchError)):
                provider_error = error.public_message
    result = await with_stop(await run_in_threadpool(recommend, wish, app.state.store, app.state.search, intent))
    result['data_mode'] = 'snapshot'
    if live_failed:
        result['warnings'].append('Онлайн-источник сейчас недоступен. Показан сохранённый каталог, а не результат свежего поиска. Попробуйте ещё раз.')
        if provider_error:
            result['warnings'].append(provider_error)
        # An explanation cannot repair a provider outage; return without another LLM wait.
        return result
    return await enrich(result, request)


if (ROOT / 'frontend/dist').exists():
    app.mount('/', StaticFiles(directory=ROOT / 'frontend/dist', html=True), name='web')
