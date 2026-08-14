from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import atomic_write_json, find_ffmpeg_location


class YtDlpUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class SubtitleChoice:
    kind: str
    language: str
    available_formats: tuple[str, ...]


def _import_yt_dlp():
    try:
        import yt_dlp
    except ImportError as exc:
        raise YtDlpUnavailable(
            "yt-dlp is not installed. Run SETUP_WINDOWS.ps1 or install requirements.txt."
        ) from exc
    return yt_dlp


def _cookie_options(cookies: str | None, cookies_from_browser: str | None) -> dict[str, Any]:
    options: dict[str, Any] = {}
    if cookies:
        options["cookiefile"] = str(Path(cookies).expanduser().resolve())
    if cookies_from_browser:
        options["cookiesfrombrowser"] = (cookies_from_browser,)
    return options


def extract_metadata(
    url: str,
    *,
    cookies: str | None = None,
    cookies_from_browser: str | None = None,
    retries: int = 10,
) -> dict[str, Any]:
    yt_dlp = _import_yt_dlp()
    options: dict[str, Any] = {
        "skip_download": True,
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
        "ignoreerrors": False,
        "retries": retries,
        "fragment_retries": retries,
    }
    options.update(_cookie_options(cookies, cookies_from_browser))

    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=False)
        if not info:
            raise RuntimeError("yt-dlp returned no metadata for the URL.")
        sanitizer = getattr(downloader, "sanitize_info", None)
        return sanitizer(info) if callable(sanitizer) else info


def _match_language(available: list[str], preferences: list[str]) -> str | None:
    if not available:
        return None

    filtered = [item for item in available if item.lower() != "live_chat"]
    if not filtered:
        return None

    lower_to_original = {item.lower(): item for item in filtered}
    for preference in preferences:
        exact = lower_to_original.get(preference.lower())
        if exact:
            return exact

    for preference in preferences:
        prefix = preference.lower() + "-"
        for item in filtered:
            if item.lower().startswith(prefix):
                return item

    preferred_bases = [preference.lower().split("-", 1)[0] for preference in preferences]
    for base in preferred_bases:
        for item in filtered:
            if item.lower().split("-", 1)[0] == base:
                return item
    return filtered[0]


def choose_subtitle(info: dict[str, Any], languages: list[str]) -> SubtitleChoice | None:
    for kind, key in (("manual", "subtitles"), ("automatic", "automatic_captions")):
        available = info.get(key) or {}
        if not isinstance(available, dict):
            continue
        language = _match_language(list(available.keys()), languages)
        if not language:
            continue
        formats = []
        for item in available.get(language) or []:
            if isinstance(item, dict) and item.get("ext"):
                formats.append(str(item["ext"]))
        return SubtitleChoice(kind=kind, language=language, available_formats=tuple(dict.fromkeys(formats)))
    return None


def _subtitle_candidates(source_dir: Path, video_id: str | None = None) -> list[Path]:
    candidates: list[Path] = []
    allowed = {".vtt", ".srt", ".json3", ".ttml", ".srv3", ".xml"}
    for path in source_dir.glob("source_subtitle*"):
        if path.is_file() and path.suffix.lower() in allowed:
            candidates.append(path)
    return sorted(candidates, key=lambda path: path.stat().st_mtime_ns, reverse=True)


def download_subtitle(
    url: str,
    source_dir: str | Path,
    choice: SubtitleChoice,
    *,
    cookies: str | None = None,
    cookies_from_browser: str | None = None,
    retries: int = 10,
) -> Path:
    yt_dlp = _import_yt_dlp()
    directory = Path(source_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)

    for old in _subtitle_candidates(directory):
        old.unlink(missing_ok=True)

    options: dict[str, Any] = {
        "skip_download": True,
        "noplaylist": True,
        "quiet": False,
        "ignoreerrors": False,
        "writesubtitles": choice.kind == "manual",
        "writeautomaticsub": choice.kind == "automatic",
        "subtitleslangs": [choice.language],
        "subtitlesformat": "vtt/srt/json3/ttml/best",
        "outtmpl": str(directory / "source_subtitle.%(id)s.%(ext)s"),
        "overwrites": True,
        "retries": retries,
        "fragment_retries": retries,
    }
    options.update(_cookie_options(cookies, cookies_from_browser))

    with yt_dlp.YoutubeDL(options) as downloader:
        result = downloader.download([url])
    if result:
        raise RuntimeError(f"yt-dlp subtitle download exited with code {result}")

    candidates = _subtitle_candidates(directory)
    if not candidates:
        raise RuntimeError(
            f"Subtitle metadata existed for language {choice.language}, but no subtitle file was written."
        )

    selected = candidates[0]
    canonical = directory / f"transcript_original{selected.suffix.lower()}"
    shutil.copy2(selected, canonical)
    return canonical


def download_audio(
    url: str,
    source_dir: str | Path,
    *,
    cookies: str | None = None,
    cookies_from_browser: str | None = None,
    retries: int = 10,
) -> Path:
    yt_dlp = _import_yt_dlp()
    directory = Path(source_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)

    ffmpeg_location = find_ffmpeg_location()
    if not ffmpeg_location:
        raise RuntimeError("FFmpeg was not found. Run app.py doctor before audio fallback.")

    for old in directory.glob("reference_audio.*"):
        if old.is_file():
            old.unlink(missing_ok=True)

    options: dict[str, Any] = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": False,
        "ignoreerrors": False,
        "outtmpl": str(directory / "reference_audio.%(ext)s"),
        "overwrites": True,
        "retries": retries,
        "fragment_retries": retries,
        "ffmpeg_location": ffmpeg_location,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",
            }
        ],
    }
    options.update(_cookie_options(cookies, cookies_from_browser))

    print(f"FFmpeg selected for audio extraction: {ffmpeg_location}")
    with yt_dlp.YoutubeDL(options) as downloader:
        result = downloader.download([url])
    if result:
        raise RuntimeError(f"yt-dlp audio download exited with code {result}")

    audio = directory / "reference_audio.wav"
    if audio.is_file():
        return audio

    candidates = sorted(directory.glob("reference_audio.*"), key=lambda path: path.stat().st_mtime_ns, reverse=True)
    if not candidates:
        raise RuntimeError("Audio download completed but no output file was found.")
    return candidates[0]


def write_metadata(path: str | Path, info: dict[str, Any]) -> Path:
    keep_keys = (
        "id",
        "title",
        "description",
        "channel",
        "channel_id",
        "uploader",
        "uploader_id",
        "duration",
        "upload_date",
        "timestamp",
        "webpage_url",
        "original_url",
        "language",
        "categories",
        "tags",
        "view_count",
        "like_count",
        "availability",
        "subtitles",
        "automatic_captions",
    )
    compact = {key: info.get(key) for key in keep_keys if key in info}
    return atomic_write_json(path, compact)
