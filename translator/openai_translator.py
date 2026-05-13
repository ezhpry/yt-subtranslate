import json
import sys
import time

from openai import OpenAI

from models.types import SubtitleEntry
from translator.base import BaseTranslator
from utils.cache import (
    load_translation_cache,
    save_translation_cache,
    cache_key,
)

TEMPERATURE = 0.2
# Progressively higher temps to break deterministic empty/missing outputs
RETRY_TEMPS = [0.2, 0.3, 0.5, 0.7, 0.9]
MAX_RETRIES = len(RETRY_TEMPS) - 1


class OpenAITranslator(BaseTranslator):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-v4-flash",
        timeout: int = 120,
        debug: bool = False,
    ):
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )
        self.model = model
        self.debug = debug

    # ---- translate ----

    def translate(
        self, entries: list[SubtitleEntry], source: str, target: str,
        use_cache: bool = True,
    ) -> list[SubtitleEntry]:
        if not entries:
            return []

        texts: list[str] = []
        cache_hits: dict[str, str] = {}

        if use_cache:
            cache = load_translation_cache()
            for e in entries:
                key = cache_key(source, target, self.model, e.text)
                if key in cache:
                    cache_hits[key] = cache[key]
                else:
                    texts.append(e.text)
        else:
            cache = {}
            texts = [e.text for e in entries]

        new_translations: dict[str, str] = {}
        if texts:
            translated = self._batch(texts, source, target, mode="translate")
            for orig, t in zip(texts, translated):
                key = cache_key(source, target, self.model, orig)
                cache[key] = t
                new_translations[key] = t
            if use_cache:
                save_translation_cache(cache)

        return [
            SubtitleEntry(index=e.index, start_ms=e.start_ms, end_ms=e.end_ms,
                          text=cache[cache_key(source, target, self.model, e.text)])
            for e in entries
        ]

    # ---- correct ----

    def correct(
        self, entries: list[SubtitleEntry], language: str = "en"
    ) -> list[SubtitleEntry]:
        if not entries:
            return []

        texts = [e.text for e in entries]
        corrected = self._batch(texts, language, language, mode="correct")
        return [
            SubtitleEntry(index=e.index, start_ms=e.start_ms, end_ms=e.end_ms, text=t)
            for e, t in zip(entries, corrected)
        ]

    # ---- core engine ----

    def _batch(
        self, texts: list[str], source: str, target: str, mode: str
    ) -> list[str]:
        n = len(texts)
        if n == 1:
            return [self._single(texts[0], source, target, mode)]

        try:
            return self._call_json_api(texts, source, target, mode)
        except Exception as e:
            print(f"  Batch failed: {e}", file=sys.stderr)
            print(f"  Falling back to single-item ({n} calls)...", file=sys.stderr)
            return [self._single(t, source, target, mode) for t in texts]

    def _call_json_api(
        self, texts: list[str], source: str, target: str, mode: str
    ) -> list[str]:
        n = len(texts)
        input_obj = {str(i): t for i, t in enumerate(texts)}
        input_json = json.dumps(input_obj, ensure_ascii=False)

        if mode == "translate":
            system_prompt = (
                f"You are a professional subtitle translator. "
                f"Translate each English subtitle line into natural Chinese.\n\n"
                f"IMPORTANT: Subtitles are often fragments split across multiple lines. "
                f"A line starting with lowercase or ending abruptly is a continuation — "
                f"use context from surrounding lines to produce a complete translation.\n\n"
                f"CRITICAL: Every input MUST have a non-empty output. "
                f"If you cannot translate a fragment, output the original English text "
                f"rather than an empty string. Empty outputs are UNACCEPTABLE.\n\n"
                f"Input is a JSON object. Output a JSON object with the SAME keys.\n\n"
                f"EXAMPLE INPUT:\n"
                f'{{"0": "within large enterprises. These are", '
                f'"1": "company and team specific skills built", '
                f'"2": "for an organization."}}\n\n'
                f"EXAMPLE JSON OUTPUT:\n"
                f'{{"0": "大型企业内部。这些是", '
                f'"1": "为组织和团队构建的特定技能", '
                f'"2": "为企业打造的。"}}\n\n'
                f"RULES:\n"
                f"1. Output ALL {n} keys (0 through {n - 1}). Never skip any key.\n"
                f"2. Every value MUST be non-empty. No \"\" values allowed.\n"
                f"3. For difficult fragments, translate literally — do not leave blank.\n"
                f"4. Keep translations concise — subtitle style.\n"
                f"5. Output ONLY the JSON object, no markdown, no explanation."
            )
        else:
            system_prompt = (
                "You are a subtitle corrector. Fix transcription errors in each value.\n"
                "Input is a JSON object. Output a JSON object with the SAME keys.\n\n"
                "EXAMPLE INPUT:\n"
                '{"0": "I use cloud code", "1": "its over their"}\n\n'
                "EXAMPLE JSON OUTPUT:\n"
                '{"0": "I use Claude Code", "1": "it\'s over there"}\n\n'
                "RULES:\n"
                f"1. Output ALL {n} keys (0 through {n - 1}).\n"
                f"2. Fix only clear errors (proper nouns, homophones, punctuation).\n"
                f"3. Every value MUST be non-empty. If correct, return unchanged.\n"
                f"4. Output ONLY valid JSON, no markdown."
            )

        user_prompt = (
            f"{input_json}\n\n"
            f"ALL {n} keys required. No empty strings. No missing keys."
        )

        last_error = None
        for attempt, temp in enumerate(RETRY_TEMPS):
            try:
                result = self._try_request(
                    system_prompt, user_prompt, n, temp,
                    attempt=attempt, total=len(RETRY_TEMPS)
                )
                return result
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    delay = 2 ** attempt
                    print(f"  Retry {attempt + 1}/{MAX_RETRIES} in {delay}s "
                          f"(temp={RETRY_TEMPS[attempt + 1]}): {e}", file=sys.stderr)
                    time.sleep(delay)

        raise last_error  # type: ignore[misc]

    def _try_request(
        self, system_prompt: str, user_prompt: str, n: int, temp: float,
        attempt: int = 0, total: int = 1
    ) -> list[str]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temp,
            max_tokens=8192,
            response_format={"type": "json_object"},
            extra_body={"thinking": {"type": "disabled"}},
        )
        content = response.choices[0].message.content or ""
        finish = response.choices[0].finish_reason
        usage = response.usage
        t_in = usage.prompt_tokens if usage else "?"
        t_out = usage.completion_tokens if usage else "?"

        if self.debug:
            print(f"  [DEBUG] temp={temp} finish={finish} "
                  f"tokens(in={t_in}, out={t_out}) len={len(content)}", file=sys.stderr)

        if not content:
            raise RuntimeError("Empty response from API")
        if finish == "length":
            raise RuntimeError(f"Response truncated (finish=length)")

        if self.debug and len(content) <= 600:
            print(f"  [DEBUG] body: {content}", file=sys.stderr)

        try:
            result = json.loads(content)
        except json.JSONDecodeError as e:
            if self.debug:
                snippet = content[max(0, e.pos - 40):e.pos + 40]
                print(f"  [DEBUG] JSON error at pos {e.pos}: ...{snippet}...", file=sys.stderr)
            raise RuntimeError(f"Invalid JSON at pos {e.pos}")

        if not isinstance(result, dict):
            raise RuntimeError(f"Expected object, got {type(result).__name__}")

        missing = [i for i in range(n) if str(i) not in result]
        empty_keys = [k for k, v in result.items() if v and isinstance(v, str) and not v.strip()]
        # Also check for truly empty values that aren't strings
        truly_empty = [k for k, v in result.items() if not v or (isinstance(v, str) and not v.strip())]

        if self.debug and (missing or truly_empty):
            keys = [str(i) for i in range(n) if str(i) in result]
            print(f"  [DEBUG] keys={len(result)}/{n}"
                  f"{' missing=' + str(missing[:10]) if missing else ''}"
                  f"{' empty=' + str(truly_empty[:10]) if truly_empty else ''}",
                  file=sys.stderr)

        if missing:
            raise RuntimeError(f"Missing keys: {missing[:10]}")
        if truly_empty:
            raise RuntimeError(f"Empty values: {truly_empty[:10]}")

        return [str(result[str(i)]) for i in range(n)]

    def _single(
        self, text: str, source: str, target: str, mode: str
    ) -> str:
        """Single-item with same progressive-temperature retry."""
        if mode == "correct":
            sys_msg = (
                "Fix transcription errors in this subtitle line. "
                "Fix only clear errors (proper nouns, homophones). "
                "Output ONLY the corrected text, no explanation."
            )
        else:
            sys_msg = (
                f"Translate this line from {source} to {target}. "
                "This may be a sentence fragment. Translate it literally — "
                "never output empty. If unsure, output the closest possible translation. "
                "Output ONLY the translation, no extra text."
            )

        last_error = None
        for attempt, temp in enumerate(RETRY_TEMPS):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": sys_msg},
                        {"role": "user", "content": text},
                    ],
                    temperature=temp,
                    extra_body={"thinking": {"type": "disabled"}},
                )
                result = (response.choices[0].message.content or "").strip()
                if not result:
                    raise RuntimeError("Empty response")
                return result
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)

        # Absolute last resort: return original text rather than empty
        print(f"  Single-item exhausted retries, returning original: {text[:50]}", file=sys.stderr)
        return text
