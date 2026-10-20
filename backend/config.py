from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    llm_provider: str = 'gemini'
    gemini_api_key: str = ''
    gemini_model: str = 'gemini-3.5-flash-lite'
    gemini_google_search: bool = False
    live_place_search: bool = True
    osrmroute_api_key: str = ''
    twogis_api_key: str = ''
    embedding_model: str = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
    semantic_search: bool = True
    walk_speed_kmh: float = 4.5
    walk_detour_factor: float = 1.3
    # Reverse proxies in front of the app that append to X-Forwarded-For.
    # 0 trusts no header: a direct client could otherwise spoof its address.
    trusted_proxy_hops: int = 0
    data_path: Path = ROOT / 'data' / 'poi.json'
    runtime_dir: Path = ROOT / 'data' / 'runtime'
    model_cache: Path = ROOT / '.cache' / 'models'


settings = Settings()
# WGS84 bounding box: south, west, north, east. This is the supported area,
# not a claim to be the administrative city boundary.
BBOX = (51.02, 71.30, 51.23, 71.60)
CATEGORIES = {
    'park': 'Парк', 'cafe': 'Кафе', 'museum': 'Музей',
    'gallery': 'Галерея', 'attraction': 'Достопримечательность',
    'playground': 'Детская площадка', 'viewpoint': 'Смотровая площадка',
    'public_space': 'Общественное пространство',
    'computer_club': 'Компьютерный клуб', 'restaurant': 'Ресторан',
    'cinema': 'Кинотеатр', 'shopping_mall': 'Торговый центр',
    'library': 'Библиотека', 'fitness': 'Фитнес и спорт',
}
