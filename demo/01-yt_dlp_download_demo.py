"""Demo: Download a YouTube video using yt-dlp."""
from pathlib import Path

from downloader.ytdlp_downloader import YtDlpDownloader


def main():
    url = input("YouTube URL: ").strip()
    if not url:
        url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
        print(f"Using default: {url}")

    downloader = YtDlpDownloader()
    workdir = Path("output/demo01")
    info = downloader.download(url, workdir=workdir)

    print(f"\nDownloaded: {info.title}")
    print(f"  ID:       {info.id}")
    print(f"  Path:     {info.path}")
    print(f"  Duration: {info.duration:.1f}s")
    print(f"  Size:     {info.path.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
