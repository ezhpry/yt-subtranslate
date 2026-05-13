import tempfile
from pathlib import Path

import yt_dlp

from models.types import VideoInfo, Subtitle
from subtitler.base import BaseSubtitler, SubtitleDownloadError


class YtDlpSubtitle(BaseSubtitler):
    def extract(self, video: VideoInfo) -> Subtitle | None:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en"],
            "subtitlesformat": "srt",
            "skip_download": True,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts["outtmpl"] = str(Path(tmpdir) / "%(id)s")
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f"https://www.youtube.com/watch?v={video.id}"])
            except Exception as e:
                raise SubtitleDownloadError(f"Failed to download subtitles: {e}")

            # Look for .srt or .vtt files
            tmp = Path(tmpdir)
            sub_files = list(tmp.glob("*.en.srt")) + list(tmp.glob("*.en.vtt"))

            if not sub_files:
                return None

            sub_file = sub_files[0]
            ext = sub_file.suffix
            if ext == ".srt":
                return Subtitle.from_srt(sub_file, language="en")
            elif ext == ".vtt":
                return Subtitle.from_vtt(sub_file, language="en")
            else:
                return None
