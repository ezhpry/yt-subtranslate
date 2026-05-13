import tempfile
from pathlib import Path

import yt_dlp

from models.types import VideoInfo, Subtitle
from subtitler.base import BaseSubtitler, SubtitleDownloadError
from utils.logger import log_info


class YtDlpSubtitle(BaseSubtitler):
    def __init__(self, language: str = "en"):
        self.language = language

    def extract(self, video: VideoInfo) -> Subtitle | None:
        # Prefer manual subtitles over auto-generated
        result = self._download(video, auto=False)
        if result is not None:
            log_info("SUBTITLE", f"Using manual {self.language} subtitles")
            return result

        log_info("SUBTITLE", f"No manual {self.language} subtitles, trying auto-generated...")
        result = self._download(video, auto=True)
        if result is not None:
            log_info("SUBTITLE", f"Using auto-generated {self.language} subtitles")
        return result

    def _download(self, video: VideoInfo, auto: bool) -> Subtitle | None:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "subtitleslangs": [self.language],
            "subtitlesformat": "srt",
            "skip_download": True,
        }
        if auto:
            ydl_opts["writeautomaticsub"] = True
        else:
            ydl_opts["writesubtitles"] = True

        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts["outtmpl"] = str(Path(tmpdir) / "%(id)s")
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f"https://www.youtube.com/watch?v={video.id}"])
            except Exception as e:
                raise SubtitleDownloadError(f"Failed to download subtitles: {e}")

            tmp = Path(tmpdir)
            lang = self.language
            sub_files = list(tmp.glob(f"*.{lang}.srt")) + list(tmp.glob(f"*.{lang}.vtt"))

            if not sub_files:
                return None

            sub_file = sub_files[0]
            ext = sub_file.suffix
            if ext == ".srt":
                return Subtitle.from_srt(sub_file, language=lang)
            elif ext == ".vtt":
                return Subtitle.from_vtt(sub_file, language=lang)
            else:
                return None
