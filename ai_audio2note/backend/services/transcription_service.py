"""
Audio transcription service backed by faster-whisper.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

try:
    from faster_whisper import WhisperModel
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise RuntimeError(
        "未检测到 faster-whisper，请运行 `pip install faster-whisper` 后重试。"
    ) from exc

_MODEL_CACHE: Dict[str, WhisperModel] = {}


def _get_model(model_size: str) -> WhisperModel:
    model = _MODEL_CACHE.get(model_size)
    if model:
        return model
    model = WhisperModel(model_size, device="auto", compute_type="auto")
    _MODEL_CACHE[model_size] = model
    return model


class TranscriptionService:
    """使用 faster-whisper 将音频转写为文本的服务。"""

    def __init__(self, model_size: str = "base"):
        self.default_model_size = model_size

    def transcribe_audio(
        self,
        audio_path: str,
        model_size: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[str, Dict[str, str]]:
        """
        转写音频文件为文本。

        Args:
            audio_path: 音频文件路径
            model_size: 使用的 Whisper 模型（默认 base）
            progress_callback: 可选进度回调

        Returns:
            (text, metadata) 元组，其中 metadata 包含语言和时长信息。
        """
        path = Path(audio_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        chosen_model = model_size or self.default_model_size
        if progress_callback:
            progress_callback(f"正在加载模型（{chosen_model}）...")

        model = _get_model(chosen_model)
        segments, info = model.transcribe(
            str(path),
            beam_size=1,
            vad_filter=True,
            compression_ratio_threshold=2.4,
        )

        lines: list[str] = []
        last_reported = 0.0
        for segment in segments:
            text = segment.text.strip()
            if text:
                lines.append(text)
            if progress_callback and segment.end and segment.end - last_reported >= 5:
                last_reported = segment.end
                progress_callback(f"已处理 {segment.end:.1f} 秒音频")

        transcript = "\n".join(lines).strip()
        metadata = {
            "language": info.language or "未知",
            "duration": f"{info.duration:.1f}s" if info.duration else "",
            "model": chosen_model,
        }
        return transcript, metadata


__all__ = ["TranscriptionService"]

