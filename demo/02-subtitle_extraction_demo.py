"""Demo: Extract English subtitles from a downloaded YouTube video."""
from pathlib import Path

from downloader.ytdlp_downloader import YtDlpDownloader
from subtitler.ytdlp_subtitle import YtDlpSubtitle
from subtitler.whisper_subtitle import WhisperSubtitle


def main():
    url = input("YouTube URL: ").strip()
    if not url:
        url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
        print(f"Using default: {url}")

    # Step 1: Download
    downloader = YtDlpDownloader()
    workdir = Path("output/demo02")
    video = downloader.download(url, workdir=workdir)
    print(f"Downloaded: {video.title}")

    # Step 2: Try downloading subtitles first
    yt_sub = YtDlpSubtitle()
    subtitle = yt_sub.extract(video)

    if subtitle is not None:
        print(f"Found YouTube captions: {len(subtitle.entries)} entries")
    else:
        # Step 3: Fallback to Whisper
        print("No captions found. Running speech recognition (model: tiny)...")
        whisper = WhisperSubtitle(model_name="tiny")
        subtitle = whisper.extract(video)
        if subtitle:
            print(f"Transcribed: {len(subtitle.entries)} segments")
        else:
            print("Failed to generate subtitles.")
            return

    # Step 4: Save
    srt_path = workdir / "en.srt"
    subtitle.to_srt(srt_path)
    print(f"Saved to: {srt_path}")
    print(f"\nFirst 3 entries:")
    for e in subtitle.entries[:3]:
        print(f"  [{e.start_ms}ms -> {e.end_ms}ms] {e.text}")


if __name__ == "__main__":
    main()
