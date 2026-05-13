from dataclasses import dataclass, field

from models.types import SubtitleStyle


@dataclass
class Settings:
    whisper_model: str = "small"
    chunk_size: int = 50
    subtitle_style: SubtitleStyle = field(default_factory=SubtitleStyle)
    api_base_url: str = ""
    api_key: str = ""
    api_timeout: int = 60
