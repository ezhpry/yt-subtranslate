import os
from pathlib import Path

import yt_dlp

from config.settings import Settings
from downloader.ytdlp_downloader import YtDlpDownloader
from models.types import VideoInfo, Subtitle, PipelineResult
from subtitler.ytdlp_subtitle import YtDlpSubtitle
from subtitler.whisper_subtitle import WhisperSubtitle
from subtitler.base import SubtitleDownloadError, SubtitleNotFoundError
from translator.openai_translator import OpenAITranslator
from compositor.ffmpeg_compositor import FFmpegCompositor
from utils.logger import log_info, log_warn, log_error


class Pipeline:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.downloader = YtDlpDownloader()
        self.yt_subtitler = YtDlpSubtitle()
        self.compositor = FFmpegCompositor()

    def run(
        self,
        url: str,
        workdir: Path | None = None,
        resolution: str = "1080p",
        subtitle_mode: str = "bilingual",
        native_zh: bool = False,
        correct_en: bool = False,
        no_cache: bool = False,
        debug: bool = False,
        translate_mode: str = "batch",
    ) -> PipelineResult:
        warnings: list[str] = []

        # Resolve video ID and workdir
        ydl_opts = {"quiet": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_id = info["id"]
        if workdir is None:
            workdir = Path(f"output/{video_id}")
        workdir.mkdir(parents=True, exist_ok=True)

        # Stage 1: Download (skip if exists)
        video_path = workdir / f"{video_id}.mp4"
        if video_path.exists():
            log_info("DOWNLOAD", f"video exists, skipping: {video_path}")
            video = VideoInfo(
                id=video_id,
                title=video_path.stem,
                path=video_path,
                duration=0,
                resolution=resolution,
                workdir=workdir,
            )
        else:
            log_info("DOWNLOAD", f"Downloading: {url}")
            try:
                video = self.downloader.download(url, workdir=workdir, resolution=resolution)
            except Exception as e:
                log_error("DOWNLOAD", str(e))
                return PipelineResult(
                    success=False,
                    video_path=Path(),
                    burned_video=None,
                    subtitle_path=None,
                    warnings=warnings,
                )
            log_info("DOWNLOAD", f"success: {video.path.name}")

        # Stage 2: Subtitles (skip if en.srt exists)
        en_srt_path = workdir / "en.srt"
        subtitle: Subtitle | None = None
        if en_srt_path.exists():
            log_info("SUBTITLE", f"en.srt exists, skipping: {en_srt_path}")
            subtitle = Subtitle.from_srt(en_srt_path, language="en")
            subtitle.normalize_timing()
            subtitle.to_srt(en_srt_path)
        else:
            log_info("SUBTITLE", "Checking for captions...")
            try:
                subtitle = self.yt_subtitler.extract(video)
            except (SubtitleDownloadError, SubtitleNotFoundError) as e:
                log_warn("SUBTITLE", f"YouTube captions failed: {e}")
                subtitle = None

            if subtitle is None:
                model_name = self.settings.whisper_model
                log_info("SUBTITLE", f"No captions, falling back to Whisper (model: {model_name})...")
                whisper = WhisperSubtitle(model_name=model_name)
                try:
                    subtitle = whisper.extract(video)
                except Exception as e:
                    log_error("SUBTITLE", f"Whisper failed: {e}")
                    warnings.append(f"Subtitle generation failed: {e}")
                    subtitle = None

            if subtitle is not None:
                subtitle.normalize_timing()
                subtitle.to_srt(en_srt_path)
                log_info("SUBTITLE", f"saved: {en_srt_path}")
            else:
                warnings.append("No English subtitles could be obtained")
                return PipelineResult(
                    success=True,
                    video_path=video.path,
                    burned_video=None,
                    subtitle_path=None,
                    warnings=warnings,
                )

        # Stage 2.5: AI correction of English subtitles (if enabled)
        if correct_en:
            api_key = self.settings.api_key or os.environ.get("DEEPSEEK_API_KEY", "")
            base_url = self.settings.api_base_url or os.environ.get(
                "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
            )
            if not api_key:
                log_warn("CORRECT", "No API key — skipping EN correction")
            else:
                corrector = OpenAITranslator(api_key=api_key, base_url=base_url, timeout=self.settings.api_timeout, debug=debug)
                chunk_size = self.settings.chunk_size
                corrected_entries: list = []
                total_chunks = (len(subtitle.entries) + chunk_size - 1) // chunk_size

                for i in range(0, len(subtitle.entries), chunk_size):
                    chunk = subtitle.entries[i:i + chunk_size]
                    chunk_num = i // chunk_size + 1
                    log_info("CORRECT", f"chunk {chunk_num}/{total_chunks} ({len(chunk)} entries)")
                    try:
                        fixed = corrector.correct(chunk, language="en")
                        corrected_entries.extend(fixed)
                    except Exception as e:
                        log_warn("CORRECT", f"chunk {chunk_num} failed: {e}, using original")
                        corrected_entries.extend(chunk)

                subtitle = Subtitle(entries=corrected_entries, language="en")
                subtitle.normalize_timing()
                subtitle.to_srt(en_srt_path)
                log_info("CORRECT", f"EN correction complete, saved: {en_srt_path}")

        # Stage 2.6: Try native Chinese subtitles (if enabled)
        zh_srt_path = workdir / "zh.srt"
        zh_subtitle: Subtitle | None = None
        if native_zh and not zh_srt_path.exists():
            log_info("SUBTITLE", "Trying native Chinese subtitles...")
            zh_native = YtDlpSubtitle(language="zh")
            try:
                zh_subtitle = zh_native.extract(video)
            except SubtitleDownloadError as e:
                log_warn("SUBTITLE", f"Native zh subtitle download failed: {e}")

            if zh_subtitle is not None:
                zh_subtitle.normalize_timing()
                zh_subtitle.to_srt(zh_srt_path)
                log_info("SUBTITLE", f"Native Chinese subtitles found: {len(zh_subtitle.entries)} entries")
                warnings.append("Using native YouTube Chinese subtitles (quality may be low)")
            else:
                log_info("SUBTITLE", "No native Chinese subtitles available")

        # Stage 3: Translate (skip if zh.srt exists)
        # Two modes: "whole" (single-request whole SRT) or "batch" (JSON chunks)
        api_key = self.settings.api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        base_url = self.settings.api_base_url or os.environ.get(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        )

        if zh_srt_path.exists():
            log_info("TRANSLATE", f"zh.srt exists, skipping: {zh_srt_path}")
            zh_subtitle = Subtitle.from_srt(zh_srt_path, language="zh")
        elif zh_subtitle is None:
            if not api_key:
                log_warn("TRANSLATE", "No API key — skipping translation")
            elif translate_mode == "whole":
                # Whole-file SRT translation — single request, bilingual output
                translator = OpenAITranslator(
                    api_key=api_key, base_url=base_url,
                    timeout=self.settings.api_timeout, debug=debug,
                )
                en_srt_text = en_srt_path.read_text(encoding="utf-8")
                log_info("TRANSLATE", f"Whole-file translation ({len(en_srt_text)} chars)...")
                try:
                    bilingual_srt = translator.translate_srt(en_srt_text)
                    zh_subtitle = Subtitle.from_srt_content(bilingual_srt, language="bilingual")
                    zh_subtitle.normalize_timing()
                    zh_subtitle.to_srt(zh_srt_path)
                    log_info("TRANSLATE", f"Whole-file complete: {len(zh_subtitle.entries)} entries")
                except Exception as e:
                    log_error("TRANSLATE", f"Whole-file failed: {e}. Falling back to batch.")
                    translate_mode = "batch"  # fall through to batch below

        if zh_subtitle is None and translate_mode != "whole" and api_key:
            translator = OpenAITranslator(
                api_key=api_key, base_url=base_url,
                timeout=self.settings.api_timeout, debug=debug,
            )
            chunk_size = self.settings.chunk_size
            translated_entries: list = []
            total_chunks = (len(subtitle.entries) + chunk_size - 1) // chunk_size

            for i in range(0, len(subtitle.entries), chunk_size):
                chunk = subtitle.entries[i:i + chunk_size]
                chunk_num = i // chunk_size + 1
                log_info("TRANSLATE", f"chunk {chunk_num}/{total_chunks} ({len(chunk)} entries)")
                try:
                    translated = translator.translate(chunk, source="en", target="zh", use_cache=not no_cache)
                    translated_entries.extend(translated)
                except Exception as e:
                    log_error("TRANSLATE", f"chunk {chunk_num} failed: {e}")
                    warnings.append(f"Translation chunk {chunk_num} failed, using original")
                    translated_entries.extend(chunk)

            zh_subtitle = Subtitle(entries=translated_entries, language="zh")
            zh_subtitle.normalize_timing()
            zh_subtitle.to_srt(zh_srt_path)
            log_info("TRANSLATE", f"saved: {zh_srt_path}")

        # Stage 4: Compose (skip if outputs exist)
        burned_path = workdir / "output_burned.mp4"
        soft_path = workdir / "output_zh.srt"

        # Determine which subtitle to burn
        # Whole-file mode already produces bilingual SRT
        if zh_subtitle is not None and zh_subtitle.language == "bilingual":
            burn_sub = zh_subtitle
            burn_sub.normalize_timing()
        elif zh_subtitle is not None and subtitle_mode == "bilingual":
            burn_sub = subtitle.merge_bilingual(zh_subtitle)
            burn_sub.normalize_timing()
            log_info("COMPOSE", "Bilingual subtitle mode: en + zh")
        elif zh_subtitle is not None:
            burn_sub = zh_subtitle
        else:
            burn_sub = None

        if burn_sub is not None:
            if not burned_path.exists():
                log_info("COMPOSE", "Burning subtitles...")
                self.compositor.burn_subtitles(
                    video.path, burn_sub, burned_path, style=self.settings.subtitle_style
                )
                log_info("COMPOSE", f"burned: {burned_path}")
            else:
                log_info("COMPOSE", f"burned video exists, skipping: {burned_path}")

            if burn_sub is zh_subtitle and not soft_path.exists():
                self.compositor.write_soft_subtitle(zh_subtitle, soft_path)
                log_info("COMPOSE", f"soft srt: {soft_path}")
            elif burn_sub is not zh_subtitle and not soft_path.exists():
                self.compositor.write_soft_subtitle(burn_sub, soft_path)
                log_info("COMPOSE", f"soft srt: {soft_path}")
            else:
                log_info("COMPOSE", f"soft srt exists, skipping: {soft_path}")

            final_burned: Path | None = burned_path
            final_srt: Path | None = soft_path
        else:
            final_burned = None
            final_srt = en_srt_path if subtitle else None

        log_info("PIPELINE",
                 f"done | burned: {final_burned} | srt: {final_srt} | warnings: {len(warnings)}")
        return PipelineResult(
            success=True,
            video_path=video.path,
            burned_video=final_burned,
            subtitle_path=final_srt,
            warnings=warnings,
        )
