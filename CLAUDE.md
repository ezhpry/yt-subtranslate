# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

yt-subtranslate — YouTube video downloader with AI subtitle translation. Downloads videos via yt-dlp, extracts/generates English subtitles (Whisper fallback), translates to Chinese via DeepSeek API, and composites subtitles into video via FFmpeg.

Python 3.10+ project managed with [uv](https://docs.astral.sh/uv/).

## Commands

```bash
# Download and translate a YouTube video (bilingual subtitles by default)
uv run python main.py https://youtube.com/xxx

# Chinese-only subtitles
uv run python main.py https://youtube.com/xxx --subtitle-mode chinese

# Run all tests
uv run python -m pytest tests/ -v

# Run a single test
uv run python -m pytest tests/test_downloader.py -v

# Run a demo
uv run python demo/05-cli_integration_demo.py

# Add a dependency
uv add <package>
```

## Architecture

Pipeline with 5 stages, strategy pattern for swappable backends:

```
main.py (CLI) → pipeline/pipeline.py (orchestrator)
  ├── downloader/ytdlp_downloader.py
  ├── subtitler/ (ytdlp_subtitle.py → whisper_subtitle.py fallback)
  ├── translator/openai_translator.py (OpenAI-compatible API, DeepSeek by default)
  └── compositor/ffmpeg_compositor.py (burn + soft subtitle)

models/types.py — shared dataclasses (VideoInfo, Subtitle, SubtitleEntry, PipelineResult, SubtitleStyle)
config/settings.py — defaults (whisper_model, chunk_size, subtitle_style)
utils/ — cache, retry, file_utils, time_utils, logger
```

## Key Design Decisions

- Subtitle timestamps stored as `int` milliseconds (not float) to avoid SRT precision issues
- `Subtitle.normalize_timing()` eliminates overlapping entries before SRT write
- Translation uses JSON-encoded batches (not delimited text) to prevent entry loss
- `extra_body={"thinking": {"type": "disabled"}}` — DeepSeek reasoning disabled for translation speed
- Translation cache keyed on `sha256(source:target:model:text)` — cross-video reuse
- `Pipeline.run()` has breakpoint resume: checks for existing intermediate files (en.srt, zh.srt, output_burned.mp4) and skips completed stages
- FFmpeg subtitles filter runs with `cwd` set to SRT directory to avoid Windows path escaping issues
