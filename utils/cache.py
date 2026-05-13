import json
import hashlib
from pathlib import Path


CACHE_DIR = Path(".cache")
CACHE_FILE = CACHE_DIR / "translation_cache.json"


def load_translation_cache() -> dict[str, str]:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_translation_cache(cache: dict[str, str]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def cache_key(source: str, target: str, model: str, text: str) -> str:
    raw = f"{source}:{target}:{model}:{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
