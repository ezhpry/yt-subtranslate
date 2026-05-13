from abc import ABC, abstractmethod

from models.types import SubtitleEntry


class BaseTranslator(ABC):
    @abstractmethod
    def translate(
        self, entries: list[SubtitleEntry], source: str, target: str
    ) -> list[SubtitleEntry]:
        """Translate entries, preserving index/start_ms/end_ms, replacing only text."""
        ...
