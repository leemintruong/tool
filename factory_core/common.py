from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: str | Path) -> Path:
    result = Path(path).expanduser().resolve()
    result.mkdir(parents=True, exist_ok=True)
    return result


def atomic_write_text(path: str | Path, text: str, encoding: str = "utf-8") -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".tmp", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as handle:
            handle.write(text)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def atomic_write_json(path: str | Path, data: Any) -> Path:
    return atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def read_json(path: str | Path, default: Any = None) -> Any:
    source = Path(path)
    if not source.is_file():
        return default
    with source.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def package_status(package_name: str) -> str:
    try:
        module = __import__(package_name)
    except ImportError:
        return "NOT_FOUND"

    version = getattr(module, "__version__", None)
    if version:
        return str(version)

    nested = getattr(module, "version", None)
    if nested and hasattr(nested, "__version__"):
        return str(nested.__version__)
    return "INSTALLED"


def find_ffmpeg_location() -> str | None:
    """Return a location accepted by yt-dlp.

    Prefer a system directory containing ffmpeg and ffprobe. Fall back to the
    complete imageio-ffmpeg executable path when no system installation exists.
    """
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return str(Path(system_ffmpeg).resolve().parent)

    try:
        import imageio_ffmpeg

        executable = Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve()
        if executable.is_file():
            return str(executable)
    except Exception:
        pass
    return None


def load_url_file(path: str | Path) -> list[str]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"URL file not found: {source}")

    urls: list[str] = []
    for raw_line in source.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return list(dict.fromkeys(urls))


def comma_list(value: str | Iterable[str] | None, default: list[str] | None = None) -> list[str]:
    if value is None:
        return list(default or [])
    if isinstance(value, str):
        items = value.split(",")
    else:
        items = list(value)
    return [str(item).strip() for item in items if str(item).strip()]
