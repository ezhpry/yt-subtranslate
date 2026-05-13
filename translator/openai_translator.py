import re
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

    # ---- translate ----

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
            translated = self._batch(texts_to_translate, self._prompt_translate(source, target))
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

    # ---- correct ----

    def correct(
        self, entries: list[SubtitleEntry], language: str = "en"
    ) -> list[SubtitleEntry]:
        if not entries:
            return []

        texts = [e.text for e in entries]
        corrected_texts = self._batch(texts, self._prompt_correct(language))

        result = []
        for e, corrected_text in zip(entries, corrected_texts):
            result.append(SubtitleEntry(
                index=e.index,
                start_ms=e.start_ms,
                end_ms=e.end_ms,
                text=corrected_text,
            ))
        return result

    # ---- batch engine (numbered format + single-item fallback) ----

    def _batch(self, texts: list[str], prompt: tuple[str, str]) -> list[str]:
        """Batch translate/correct using numbered format. Falls back to single-item."""
        n = len(texts)
        if n == 1:
            return [self._single_item(texts[0], prompt)]

        system_prompt, task_hint = prompt
        try:
            return self._call_numbered(texts, system_prompt, task_hint)
        except Exception as e:
            print(f"  Batch failed: {e}", file=sys.stderr)
            print(f"  Falling back to single-item ({n} calls)...", file=sys.stderr)
            return [self._single_item(t, prompt) for t in texts]

    def _single_item(self, text: str, prompt: tuple[str, str]) -> str:
        """Translate or correct a single item — most reliable."""
        system_prompt, _task_hint = prompt

        def do_request():
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
                extra_body={"thinking": {"type": "disabled"}},
            )
            result = (response.choices[0].message.content or "").strip()
            if not result:
                raise RuntimeError("Empty response")
            return result

        return retry_with_backoff(do_request, max_retries=2)

    def _call_numbered(
        self, texts: list[str], system_prompt: str, task_hint: str
    ) -> list[str]:
        """Use numbered format: [1] text → [1] result. Model handles this naturally."""
        n = len(texts)
        numbered_input = "\n".join(f"[{i + 1}] {t}" for i, t in enumerate(texts))

        user_prompt = (
            f"{numbered_input}\n\n"
            f"{task_hint}\n"
            f"There are exactly {n} items above. Output exactly {n} lines "
            f"with numbers [1] through [{n}]."
        )

        def do_request():
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                extra_body={"thinking": {"type": "disabled"}},
            )
            raw = response.choices[0].message.content or ""
            finish = response.choices[0].finish_reason
            if finish == "length":
                raise RuntimeError("Response truncated by token limit")

            # Parse numbered output
            parsed = {}
            for line in raw.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                m = re.match(r"^\[(\d+)\]\s*(.+)$", line)
                if m:
                    parsed[int(m.group(1))] = m.group(2).strip()

            # Validate
            missing = [i for i in range(1, n + 1) if i not in parsed]
            if missing:
                raise RuntimeError(f"Missing: {missing}. Got {len(parsed)}/{n}")

            return [parsed[i] for i in range(1, n + 1)]

        return retry_with_backoff(do_request, max_retries=2)

    # ---- prompts ----

    def _prompt_translate(self, source: str, target: str) -> tuple[str, str]:
        system = (
            f"You are a professional subtitle translator. "
            f"Translate each line from {source} to {target}. "
            f"Keep translations concise and natural — subtitle style."
        )
        task = (
            f"Translate the {source} lines above to {target}. "
            f"Keep the same format: [1] translation, [2] translation, ..."
        )
        return (system, task)

    def _prompt_correct(self, language: str) -> tuple[str, str]:
        system = (
            "You are a subtitle transcription corrector. "
            "Auto-generated subtitles often have errors: "
            "misrecognized proper nouns (e.g., 'cloud code' → 'Claude Code'), "
            "homophones (their/there), missing punctuation. "
            "Fix only clear errors using context. "
            "If the text is correct, return it unchanged. "
            "Keep the same length — this is subtitle text."
        )
        task = (
            "Review and correct each line above for transcription errors. "
            "Keep the same format: [1] corrected, [2] corrected, ..."
        )
        return (system, task)
