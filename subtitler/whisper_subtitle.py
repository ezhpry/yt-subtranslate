from models.types import VideoInfo, Subtitle
from subtitler.base import BaseSubtitler


class WhisperSubtitle(BaseSubtitler):
    def __init__(self, model_name: str = "small"):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            import whisper
            self._model = whisper.load_model(self.model_name)
        return self._model

    def extract(self, video: VideoInfo) -> Subtitle | None:
        result = self.model.transcribe(str(video.path), language="en")
        segments = result.get("segments", [])
        if not segments:
            return None
        return Subtitle.from_whisper_segments(segments, language="en")
