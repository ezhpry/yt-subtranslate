"""Demo: Full pipeline - download, subtitle, translate, compose."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.pipeline import Pipeline


def main():
    url = input("YouTube URL: ").strip()
    if not url:
        url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
        print(f"Using default: {url}")

    print(f"\nStarting full pipeline for: {url}\n")
    pipeline = Pipeline()
    result = pipeline.run(url, resolution="720p")

    print(f"\n{'=' * 50}")
    print(f"Result: {'SUCCESS' if result.success else 'FAILED'}")
    print(f"  Video:    {result.video_path}")
    print(f"  Burned:   {result.burned_video}")
    print(f"  Subtitle: {result.subtitle_path}")
    if result.warnings:
        print(f"  Warnings: {len(result.warnings)}")
        for w in result.warnings:
            print(f"    - {w}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
