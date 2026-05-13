import subprocess
from pathlib import Path

from models.types import Subtitle, SubtitleStyle


class FFmpegCompositor:
    def burn_subtitles(
        self,
        video_path: Path,
        subtitle: Subtitle,
        output_path: Path,
        style: SubtitleStyle | None = None,
    ) -> Path:
        """Burn subtitles into video using FFmpeg subtitles filter."""
        style = style or SubtitleStyle()

        # Write SRT alongside output so we can use a simple relative filename
        # (FFmpeg subtitles filter has path-escaping issues on Windows)
        srt_path = output_path.parent / f"{output_path.stem}.temp.srt"
        subtitle.to_srt(srt_path)

        # Use just the filename — run ffmpeg with cwd set to the SRT directory
        srt_name = srt_path.name
        vf = (
            f"subtitles='{srt_name}':"
            f"force_style='FontSize={style.font_size},"
            f"PrimaryColour=&H{_color_to_hex(style.font_color)},"
            f"OutlineColour=&H{_color_to_hex(style.outline_color)}'"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path.resolve()),
            "-vf", vf,
            "-c:a", "copy",
            str(output_path.name),
        ]
        subprocess.run(
            cmd, check=True, capture_output=True, text=True,
            cwd=str(srt_path.parent),
        )

        srt_path.unlink(missing_ok=True)
        return output_path

    def write_soft_subtitle(self, subtitle: Subtitle, output_path: Path) -> Path:
        """Write subtitle as standalone SRT file."""
        subtitle.to_srt(output_path)
        return output_path


def _color_to_hex(color: str) -> str:
    """Convert color name to BGR hex for FFmpeg ASS (AABBGGRR format)."""
    colors = {
        "white": "00FFFFFF",
        "black": "00000000",
        "red": "000000FF",
        "green": "0000FF00",
        "blue": "00FF0000",
        "yellow": "0000FFFF",
    }
    return colors.get(color.lower(), "00FFFFFF")
