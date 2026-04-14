import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "SilverCare Medical Companion Agent")
    app_version: str = os.getenv("APP_VERSION", "0.2.0")
    demo_reference_date: date = date.fromisoformat(
        os.getenv("REFERENCE_DATE", date.today().isoformat())
    )
    default_city: str = os.getenv("DEFAULT_CITY", "上海")
    default_check_in_buffer_minutes: int = int(os.getenv("CHECK_IN_BUFFER_MINUTES", "30"))
    realtime_route_limit: int = int(os.getenv("REALTIME_ROUTE_LIMIT", "3"))
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./silvercare.db")
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
    ollama_timeout_seconds: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))
    ollama_think: bool = _as_bool(os.getenv("OLLAMA_THINK"), default=False)
    ollama_num_predict: int = int(os.getenv("OLLAMA_NUM_PREDICT", "120"))
    ollama_keep_alive: str = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
    warm_ollama_on_startup: bool = _as_bool(os.getenv("WARM_OLLAMA_ON_STARTUP"), default=True)
    ollama_executable: str = os.getenv(
        "OLLAMA_EXECUTABLE",
        str(Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe"),
    )
    auto_start_ollama: bool = _as_bool(os.getenv("AUTO_START_OLLAMA"), default=True)
    ollama_startup_timeout_seconds: int = int(os.getenv("OLLAMA_STARTUP_TIMEOUT_SECONDS", "20"))
    allow_rule_triage_fallback: bool = _as_bool(
        os.getenv("ALLOW_RULE_TRIAGE_FALLBACK"), default=True
    )
    map_provider: str = os.getenv("MAP_PROVIDER", "amap")
    amap_api_key: str = os.getenv("AMAP_API_KEY", "")
    amap_base_url: str = os.getenv("AMAP_BASE_URL", "https://restapi.amap.com")
    nearby_search_radius_meters: int = int(os.getenv("NEARBY_SEARCH_RADIUS_METERS", "15000"))
    nearby_search_pages: int = int(os.getenv("NEARBY_SEARCH_PAGES", "3"))
    nearby_hospital_limit: int = int(os.getenv("NEARBY_HOSPITAL_LIMIT", "18"))
    max_candidate_results: int = int(os.getenv("MAX_CANDIDATE_RESULTS", "3"))
    server_host: str = os.getenv("SERVER_HOST", "127.0.0.1")
    server_port: int = int(os.getenv("SERVER_PORT", "8000"))


settings = Settings()
