"""Demo: Translate English subtitles to Chinese using DeepSeek."""
import os
from pathlib import Path

from models.types import Subtitle
from translator.deepseek_translator import DeepSeekTranslator


def main():
    srt_path = input("SRT file path: ").strip()
    if not srt_path:
        srt_path = "output/demo02/en.srt"
        print(f"Using default: {srt_path}")

    srt_path = Path(srt_path)
    if not srt_path.exists():
        print(f"File not found: {srt_path}")
        return

    subtitle = Subtitle.from_srt(srt_path, language="en")
    print(f"Loaded {len(subtitle.entries)} entries from {srt_path}")

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    if not api_key:
        print("Set DEEPSEEK_API_KEY environment variable")
        return

    translator = DeepSeekTranslator(api_key=api_key, base_url=base_url, model="deepseek-v4-pro")

    chunk_size = 50
    translated_entries = []
    total_chunks = (len(subtitle.entries) + chunk_size - 1) // chunk_size

    for i in range(0, len(subtitle.entries), chunk_size):
        chunk = subtitle.entries[i:i + chunk_size]
        chunk_num = i // chunk_size + 1
        print(f"Translating chunk {chunk_num}/{total_chunks} ({len(chunk)} entries)...")
        translated_chunk = translator.translate(chunk, source="en", target="zh")
        translated_entries.extend(translated_chunk)

    zh_subtitle = Subtitle(entries=translated_entries, language="zh")
    out_path = srt_path.parent / "zh.srt"
    zh_subtitle.to_srt(out_path)
    print(f"\nSaved to: {out_path}")
    print("First 3 translations:")
    for e in translated_entries[:3]:
        print(f"  {e.text}")


if __name__ == "__main__":
    main()
