import re
import subprocess
import wave
from pathlib import Path
from .env_check import get_ffmpeg_bin, get_ffprobe_bin


def _wav_duration(audio_path: str) -> float:
    with wave.open(audio_path, "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        if rate <= 0:
            raise ValueError("Invalid WAV sample rate")
        return frames / float(rate)


def _parse_ffmpeg_duration(stderr_text: str) -> float:
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr_text)
    if not m:
        raise RuntimeError("Không đọc được duration từ ffmpeg output.")
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def get_audio_duration(audio_path: str) -> float:
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Không thấy file voice/audio: {audio_path}")

    if path.suffix.lower() == ".wav":
        return _wav_duration(str(path))

    ffprobe = get_ffprobe_bin()
    if ffprobe:
        cmd = [
            ffprobe, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())

    ffmpeg = get_ffmpeg_bin()
    result = subprocess.run([ffmpeg, "-i", str(path)], capture_output=True, text=True, check=False)
    return _parse_ffmpeg_duration(result.stderr or result.stdout or "")


def has_audio(path: str) -> bool:
    return Path(path).exists() and Path(path).stat().st_size > 0
