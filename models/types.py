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
class SubtitleStyle:
    font_size: int = 24
    font_color: str = "white"
    outline_color: str = "black"
