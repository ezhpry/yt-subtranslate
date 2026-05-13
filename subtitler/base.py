from abc import ABC, abstractmethod

from models.types import VideoInfo, Subtitle


class SubtitleNotFoundError(Exception):
    """Raised when no subtitles are available for the video."""
    pass


class SubtitleDownloadError(Exception):
    """Raised when subtitle download fails due to network or parsing error."""
    pass


class BaseSubtitler(ABC):
    @abstractmethod
    def extract(self, video: VideoInfo) -> Subtitle | None:
        """Returns None if no subtitles available. Raises on download failure."""
        ...
