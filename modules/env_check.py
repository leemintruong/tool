import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional


def _imageio_ffmpeg_path() -> Optional[str]:
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and Path(path).exists():
            return str(path)
    except Exception:
        return None
    return None


def get_ffmpeg_bin() -> str:
    """Return an ffmpeg executable path.

    Priority:
    1) System PATH ffmpeg
    2) imageio-ffmpeg bundled ffmpeg from pip package
    """
    path = shutil.which("ffmpeg")
    if path:
        return path
    bundled = _imageio_ffmpeg_path()
    if bundled:
        return bundled
    raise RuntimeError(
        "Không tìm thấy FFmpeg. Cách dễ nhất: chạy `pip install imageio-ffmpeg` trong venv, "
        "hoặc cài FFmpeg vào PATH."
    )


def get_ffprobe_bin() -> Optional[str]:
    path = shutil.which("ffprobe")
    return path


def find_piper_bin(explicit: str | None = None) -> Optional[str]:
    """Find Piper, including the executable installed inside the active venv."""
    candidates: list[Path] = []
    if explicit and explicit != "piper":
        candidates.append(Path(explicit).expanduser())

    scripts_dir = Path(sys.executable).resolve().parent
    candidates.extend((scripts_dir / "piper.exe", scripts_dir / "piper"))

    path_piper = shutil.which(explicit or "piper")
    if path_piper:
        candidates.append(Path(path_piper))

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return str(resolved)
    return None


def get_piper_bin(explicit: str | None = None) -> str:
    path = find_piper_bin(explicit)
    if path:
        return path
    raise RuntimeError(
        "Không tìm thấy Piper. Hãy chạy INSTALL_PIPER_WINDOWS.bat, sau đó chạy app.py doctor."
    )


def piper_status() -> str:
    path = find_piper_bin()
    if not path:
        return "NOT_FOUND (run INSTALL_PIPER_WINDOWS.bat)"
    try:
        package_version = version("piper-tts")
    except PackageNotFoundError:
        package_version = "unknown"
    return f"{path} | piper-tts {package_version}"


def _version_with_path(path: str) -> str:
    try:
        result = subprocess.run([path, "-version"], capture_output=True, text=True, check=False)
        first = (result.stdout or result.stderr).splitlines()[0] if (result.stdout or result.stderr) else "FOUND"
        return f"{path} | {first}"
    except Exception as e:
        return f"{path} | ERROR: {e}"


def check_environment() -> dict:
    try:
        ffmpeg_info = _version_with_path(get_ffmpeg_bin())
    except Exception as e:
        ffmpeg_info = f"NOT_FOUND | {e}"

    ffprobe = get_ffprobe_bin()
    ffprobe_info = _version_with_path(ffprobe) if ffprobe else "NOT_FOUND (OK nếu dùng voice .wav; V7.1 không bắt buộc ffprobe)"

    try:
        import imageio_ffmpeg
        imageio_info = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        imageio_info = f"NOT_AVAILABLE | {e}"

    return {
        "ffmpeg": ffmpeg_info,
        "ffprobe": ffprobe_info,
        "imageio_ffmpeg": imageio_info,
        "piper": piper_status(),
        "cwd": str(Path.cwd()),
    }


def require_ffmpeg() -> None:
    get_ffmpeg_bin()
