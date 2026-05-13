"""YouTube video downloader with AI subtitle translation."""
import argparse
import sys

from pipeline.pipeline import Pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Download YouTube videos and translate subtitles"
    )
    parser.add_argument("url", nargs="?", help="YouTube URL")
    parser.add_argument("--resolution", default="1080p", help="Video resolution")
    parser.add_argument(
        "--whisper-model", default="small",
        choices=["tiny", "base", "small", "medium"],
    )
    parser.add_argument("--chunk-size", type=int, default=None, help="Translation batch size (default: 15)")
    parser.add_argument("--font-size", type=int, default=24)
    parser.add_argument("--font-color", default="white")
    parser.add_argument("--outline-color", default="black")
    parser.add_argument(
        "--subtitle-mode", default="bilingual",
        choices=["chinese", "bilingual"],
        help="Subtitle display mode (default: bilingual)",
    )
    parser.add_argument(
        "--native-zh", action="store_true",
        help="Use YouTube's built-in Chinese subtitles (lower quality, skips AI translation)",
    )
    parser.add_argument(
        "--correct-en", action="store_true",
        help="AI-correction of English subtitles before translation (fixes transcription errors)",
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="Disable translation cache (force re-translate)",
    )

    args = parser.parse_args()

    if not args.url:
        parser.print_help()
        sys.exit(1)

    pipeline = Pipeline()
    if args.chunk_size is not None:
        pipeline.settings.chunk_size = args.chunk_size
    result = pipeline.run(
        url=args.url,
        resolution=args.resolution,
        subtitle_mode=args.subtitle_mode,
        native_zh=args.native_zh,
        correct_en=args.correct_en,
        no_cache=args.no_cache,
    )

    if result.success:
        print(f"\nDone!")
        print(f"  Video:    {result.video_path}")
        if result.burned_video:
            print(f"  Burned:   {result.burned_video}")
        if result.subtitle_path:
            print(f"  Subtitle: {result.subtitle_path}")
        for w in result.warnings:
            print(f"  [WARN] {w}")
        sys.exit(0)
    else:
        print("Failed!", file=sys.stderr)
        for w in result.warnings:
            print(f"  [WARN] {w}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
