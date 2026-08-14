from pathlib import Path
from typing import Optional

from .thumbnail_generator import create_thumbnail
from .tts_piper import create_voice_with_piper
from .video_renderer import render_video


def build_video_package(
    script_path: str,
    media_dir: str,
    out_dir: str,
    voice_path: Optional[str] = None,
    tts_model: Optional[str] = None,
    piper_bin: str = "piper",
    thumbnail_background: Optional[str] = None,
    thumbnail_text: str = "KICKED OUT",
    music_path: Optional[str] = None,
    burn_subtitles: bool = False,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    image_duration_seconds: int = 9,
    bitrate: str = "3500k",
    seed: int = 42,
) -> dict:
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    created = {}

    # 1) voice
    if voice_path:
        voice_file = voice_path
    elif tts_model:
        voice_file = str(out_root / "voice.wav")
        create_voice_with_piper(script_path, voice_file, tts_model, piper_bin)
    else:
        raise ValueError("Bạn cần truyền --voice hoặc --tts-model để có file voice.")
    created["voice"] = voice_file

    # 2) render
    final_video = render_video(
        script_path=script_path,
        voice_path=voice_file,
        media_dir=media_dir,
        out_dir=out_dir,
        music_path=music_path,
        width=width,
        height=height,
        fps=fps,
        image_duration_seconds=image_duration_seconds,
        bitrate=bitrate,
        burn_subtitles=burn_subtitles,
        seed=seed,
    )
    created["final_video"] = str(final_video)
    created["scenes"] = str(out_root / "scenes.json")
    created["subtitles"] = str(out_root / "subtitles.srt")
    created["metadata"] = str(out_root / "metadata.json")
    created["render_manifest"] = str(out_root / "render_manifest.json")

    # 3) thumbnail draft
    bg = thumbnail_background
    if not bg:
        media_files = sorted([p for p in Path(media_dir).glob("*.*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}])
        if media_files:
            bg = str(media_files[0])
    if bg:
        created["thumbnail"] = create_thumbnail(bg, thumbnail_text, str(out_root / "thumbnail.jpg"))

    return created
