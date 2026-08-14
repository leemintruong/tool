from __future__ import annotations

from pathlib import Path

from .transcript_service import TranscriptSegment


def faster_whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def transcribe_audio(
    audio_path: str | Path,
    *,
    model_name: str = "small",
    language: str | None = None,
    device: str = "cpu",
    compute_type: str = "int8",
) -> tuple[list[TranscriptSegment], dict]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper is not installed. Run INSTALL_WHISPER_WINDOWS.bat first."
        ) from exc

    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    raw_segments, info = model.transcribe(
        str(Path(audio_path).resolve()),
        language=language,
        beam_size=5,
        vad_filter=True,
    )

    segments: list[TranscriptSegment] = []
    for item in raw_segments:
        text = str(item.text).strip()
        if text:
            segments.append(TranscriptSegment(start=float(item.start), end=float(item.end), text=text))

    info_dict = {
        "language": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
        "duration": getattr(info, "duration", None),
        "duration_after_vad": getattr(info, "duration_after_vad", None),
        "model": model_name,
        "device": device,
        "compute_type": compute_type,
    }
    return segments, info_dict
