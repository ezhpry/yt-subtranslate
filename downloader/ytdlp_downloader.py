from pathlib import Path

import yt_dlp

from models.types import VideoInfo
from utils.file_utils import sanitize_filename, ensure_dir


class YtDlpDownloader:
    def download(self, url: str, workdir: Path, resolution: str = "1080p") -> VideoInfo:
        ensure_dir(workdir)
        output_template = str(workdir / "%(id)s.%(ext)s")

        ydl_opts = {
            "format": f"bestvideo[height<={resolution.rstrip('p')}]+bestaudio/best[height<={resolution.rstrip('p')}]",
            "outtmpl": output_template,
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info["id"]
            title = info.get("title", video_id)
            duration = info.get("duration", 0) or 0
            actual_resolution = info.get("resolution") or resolution
            output_path = Path(workdir / f"{video_id}.mp4")

        return VideoInfo(
            id=video_id,
            title=sanitize_filename(title),
            path=output_path,
            duration=float(duration),
            resolution=actual_resolution,
            workdir=workdir,
        )
