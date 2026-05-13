"""Demo: Compose video with translated subtitles."""
from pathlib import Path

from models.types import Subtitle
from compositor.ffmpeg_compositor import FFmpegCompositor


def main():
    video_path = input("Video file path: ").strip()
    if not video_path:
        video_path = "output/demo02/6zi75JUXB94.mp4"
        print(f"Using default video: {video_path}")

    srt_path = input("Subtitle file path (zh.srt): ").strip()
    if not srt_path:
        srt_path = "output/demo02/zh.srt"
        print(f"Using default subtitle: {srt_path}")

    video_path = Path(video_path)
    srt_path = Path(srt_path)

    if not video_path.exists():
        print(f"Video not found: {video_path}")
        return
    if not srt_path.exists():
        print(f"Subtitle not found: {srt_path}")
        return

    subtitle = Subtitle.from_srt(srt_path, language="zh")
    print(f"Loaded {len(subtitle.entries)} subtitle entries")

    compositor = FFmpegCompositor()
    out_dir = video_path.parent

    # Burn subtitles
    burned_path = out_dir / "output_burned.mp4"
    print("Burning subtitles into video...")
    compositor.burn_subtitles(video_path, subtitle, burned_path)
    print(f"Burned video: {burned_path} ({burned_path.stat().st_size / 1024 / 1024:.1f} MB)")

    # Soft subtitles
    soft_path = out_dir / "output_zh.srt"
    compositor.write_soft_subtitle(subtitle, soft_path)
    print(f"Soft subtitle: {soft_path}")


if __name__ == "__main__":
    main()
