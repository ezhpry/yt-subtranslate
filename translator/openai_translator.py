import json
import hashlib
from pathlib import Path

import urllib.request
import urllib.error

from models.types import SubtitleEntry
from translator.base import BaseTranslator
from utils.retry import retry_with_backoff


CACHE_DIR = Path(".cache")
CACHE_FILE = CACHE_DIR / "translation_cache.json"


def _load_cache() -> dict[str, str]:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict[str, str]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _cache_key(source: str, target: str, model: str, text: str) -> str:
    raw = f"{source}:{target}:{model}:{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class OpenAITranslator(BaseTranslator):
    def __init__(self, api_key: str, base_url: str, model: str = "gpt-4o-mini", timeout: int = 60):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def translate(
        self, entries: list[SubtitleEntry], source: str, target: str
    ) -> list[SubtitleEntry]:
        if not entries:
            return []

        cache = _load_cache()
        texts_to_translate = []
        cache_hits: dict[str, str] = {}

        for e in entries:
            key = _cache_key(source, target, self.model, e.text)
            if key in cache:
                cache_hits[key] = cache[key]
            else:
                texts_to_translate.append(e.text)

        new_translations: dict[str, str] = {}
        if texts_to_translate:
            translated = self._call_api(texts_to_translate, source, target)
            for original, translated_text in zip(texts_to_translate, translated):
                key = _cache_key(source, target, self.model, original)
                cache[key] = translated_text
                new_translations[key] = translated_text
            _save_cache(cache)

        all_translations = {**cache_hits, **new_translations}
        result = []
        for e in entries:
            key = _cache_key(source, target, self.model, e.text)
            result.append(SubtitleEntry(
                index=e.index,
                start_ms=e.start_ms,
                end_ms=e.end_ms,
                text=all_translations[key],
            ))
        return result

    def _call_api(self, texts: list[str], source: str, target: str) -> list[str]:
        joined = "\n---\n".join(texts)
        system_prompt = (
            f"You are a translator. Translate the following text from {source} to {target}. "
            f"Each segment is separated by '\\n---\\n'. "
            f"Return the translations in the same order, separated by '\\n---\\n'. "
            f"Output ONLY the translations, no explanations."
        )

        def do_request():
            data = json.dumps({
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": joined},
                ],
                "temperature": 0.3,
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )

            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                raise RuntimeError(f"API error: {e.code} {e.reason}")

            content = body["choices"][0]["message"]["content"]
            translated = [t.strip() for t in content.split("\n---\n")]
            if len(translated) != len(texts):
                raise RuntimeError(
                    f"Translation count mismatch: expected {len(texts)}, got {len(translated)}"
                )
            return translated

        return retry_with_backoff(do_request, max_retries=3)
