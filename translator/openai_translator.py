import sys

from openai import OpenAI

from models.types import SubtitleEntry
from translator.base import BaseTranslator
from utils.retry import retry_with_backoff
from utils.cache import (
    load_translation_cache,
    save_translation_cache,
    cache_key,
)


class OpenAITranslator(BaseTranslator):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-v4-flash",
        timeout: int = 120,
    ):
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )
        self.model = model

    def translate(
        self, entries: list[SubtitleEntry], source: str, target: str
    ) -> list[SubtitleEntry]:
        if not entries:
            return []

        cache = load_translation_cache()
        texts_to_translate: list[str] = []
        cache_hits: dict[str, str] = {}

        for e in entries:
            key = cache_key(source, target, self.model, e.text)
            if key in cache:
                cache_hits[key] = cache[key]
            else:
                texts_to_translate.append(e.text)

        new_translations: dict[str, str] = {}
        if texts_to_translate:
            translated = self._call_api(texts_to_translate, source, target)
            for original, translated_text in zip(texts_to_translate, translated):
                key = cache_key(source, target, self.model, original)
                cache[key] = translated_text
                new_translations[key] = translated_text
            save_translation_cache(cache)

        all_translations = {**cache_hits, **new_translations}
        result = []
        for e in entries:
            key = cache_key(source, target, self.model, e.text)
            result.append(SubtitleEntry(
                index=e.index,
                start_ms=e.start_ms,
                end_ms=e.end_ms,
                text=all_translations[key],
            ))
        return result

    def _call_api(
        self, texts: list[str], source: str, target: str
    ) -> list[str]:
        import json as _json

        # Build a numbered JSON input so the LLM can track each entry precisely
        items = {str(i): text for i, text in enumerate(texts)}
        user_input = _json.dumps(items, ensure_ascii=False)

        system_prompt = (
            f"You are a translator. Translate each text from {source} to {target}. "
            f"Input is a JSON object mapping numeric IDs to text. "
            f"Output a JSON object with the SAME numeric IDs mapped to translations. "
            f"Preserve all IDs exactly. Output ONLY valid JSON, no markdown, no explanations."
        )

        def do_request():
            print(f"  Sending request ({len(texts)} texts, ~{len(user_input)} chars)...", file=sys.stderr)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input},
                ],
                temperature=0.3,
                extra_body={"thinking": {"type": "disabled"}},
            )
            print(f"  Response received.", file=sys.stderr)
            content = response.choices[0].message.content or ""
            # Strip markdown code fences if present
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[-1]
                if content.endswith("```"):
                    content = content[:-3].strip()

            try:
                result = _json.loads(content)
            except _json.JSONDecodeError:
                raise RuntimeError(f"Failed to parse translation response as JSON: {content[:200]}")

            # Reconstruct in original order
            translated = []
            for i in range(len(texts)):
                key = str(i)
                if key not in result:
                    raise RuntimeError(
                        f"Missing translation for ID {key}. Got keys: {list(result.keys())[:10]}"
                    )
                translated.append(result[key])
            return translated

        return retry_with_backoff(do_request, max_retries=3)
