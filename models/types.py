from dataclasses import dataclass
from pathlib import Path


@dataclass
class VideoInfo:
    id: str
    title: str
    path: Path
    duration: float
    resolution: str
    workdir: Path


@dataclass
class SubtitleEntry:
    index: int
    start_ms: int
    end_ms: int
    text: str


@dataclass
class Subtitle:
    entries: list[SubtitleEntry]
    language: str  # ISO 639-1, e.g. "en", "zh"

    @classmethod
    def from_srt(cls, path: Path, language: str) -> "Subtitle":
        from utils.time_utils import srt_timestamp_to_ms

        entries = []
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        blocks = content.split("\n\n")
        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) < 3:
                continue
            index = int(lines[0])
            start_str, end_str = lines[1].split(" --> ")
            text = "\n".join(lines[2:])

            entries.append(SubtitleEntry(
                index=index,
                start_ms=srt_timestamp_to_ms(start_str.strip()),
                end_ms=srt_timestamp_to_ms(end_str.strip()),
                text=text,
            ))

        return cls(entries=entries, language=language)

    @classmethod
    def from_vtt(cls, path: Path, language: str) -> "Subtitle":
        from utils.time_utils import srt_timestamp_to_ms

        entries = []
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        blocks = content.strip().split("\n\n")
        idx = 0
        for block in blocks:
            if block.startswith("WEBVTT") or not block.strip():
                continue
            lines = block.strip().split("\n")
            if len(lines) < 2:
                continue
            timestamp_line = lines[0]
            if " --> " not in timestamp_line:
                if len(lines) > 1 and " --> " in lines[1]:
                    lines = lines[1:]
                    timestamp_line = lines[0]
                else:
                    continue
            start_str, end_str = timestamp_line.split(" --> ")
            text = "\n".join(lines[1:])
            idx += 1

            entries.append(SubtitleEntry(
                index=idx,
                start_ms=srt_timestamp_to_ms(start_str.strip().replace(".", ",")),
                end_ms=srt_timestamp_to_ms(end_str.strip().replace(".", ",")),
                text=text,
            ))

        return cls(entries=entries, language=language)

    @classmethod
    def from_whisper_segments(cls, segments: list[dict], language: str) -> "Subtitle":
        entries = []
        for i, seg in enumerate(segments, 1):
            entries.append(SubtitleEntry(
                index=i,
                start_ms=int(seg["start"] * 1000),
                end_ms=int(seg["end"] * 1000),
                text=seg["text"].strip(),
            ))
        return cls(entries=entries, language=language)

    def to_srt(self, path: Path) -> None:
        from utils.time_utils import ms_to_srt_timestamp

        with open(path, "w", encoding="utf-8") as f:
            for entry in self.entries:
                f.write(f"{entry.index}\n")
                f.write(f"{ms_to_srt_timestamp(entry.start_ms)} --> {ms_to_srt_timestamp(entry.end_ms)}\n")
                f.write(f"{entry.text}\n\n")

    def normalize_timing(self, min_gap_ms: int = 1) -> None:
        """Ensure entries do not overlap. Trims end_ms of overlapping entries."""
        for i in range(len(self.entries) - 1):
            current = self.entries[i]
            nxt = self.entries[i + 1]
            limit = nxt.start_ms - min_gap_ms
            if current.end_ms > limit:
                current.end_ms = limit

    def merge_bilingual(self, other: "Subtitle") -> "Subtitle":
        """Merge with another subtitle of same entry count. Pairs text as 'en\ntranslated'."""
        merged = []
        for a, b in zip(self.entries, other.entries):
            merged.append(SubtitleEntry(
                index=a.index,
                start_ms=a.start_ms,
                end_ms=a.end_ms,
                text=f"{b.text}\n{a.text}",
            ))
        return Subtitle(entries=merged, language="bilingual")


@dataclass
class SubtitleStyle:
    font_size: int = 24
    font_color: str = "white"
    outline_color: str = "black"


@dataclass
class PipelineResult:
    success: bool
    video_path: Path
    burned_video: Path | None
    subtitle_path: Path | None
    warnings: list[str]
