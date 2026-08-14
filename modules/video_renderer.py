import json
import math
import shlex
import subprocess
from pathlib import Path
from typing import List, Optional

from .audio_utils import get_audio_duration
from .env_check import require_ffmpeg, get_ffmpeg_bin
from .media_selector import choose_media, distribute_scenes, IMAGE_EXTS, VIDEO_EXTS
from .subtitle_generator import create_srt_from_script
from .metadata_generator import create_metadata
from .scene_planner import create_scene_plan


def run(cmd: List[str]) -> None:
    require_ffmpeg()
    cmd = [get_ffmpeg_bin() if c == "ffmpeg" else c for c in cmd]
    print("$ " + " ".join(shlex.quote(str(c)) for c in cmd))
    subprocess.run(cmd, check=True)


def _make_image_segment(src: Path, out: Path, duration: float, width: int, height: int, fps: int, bitrate: str) -> None:
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={fps},format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-t", f"{duration:.3f}", "-i", str(src),
        "-vf", vf,
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-b:v", bitrate,
        str(out),
    ]
    run(cmd)


def _make_video_segment(src: Path, out: Path, duration: float, width: int, height: int, fps: int, bitrate: str) -> None:
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={fps},format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y", "-stream_loop", "-1", "-t", f"{duration:.3f}", "-i", str(src),
        "-vf", vf,
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-b:v", bitrate,
        str(out),
    ]
    run(cmd)


def _concat_segments(segments: List[Path], out: Path) -> None:
    if not segments:
        raise RuntimeError("No rendered segments were created.")
    list_file = out.parent / "segments.txt"
    lines = []
    for segment in segments:
        escaped = segment.resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", str(out)
    ]
    run(cmd)


def _merge_audio(video_silent: Path, voice: Path, out: Path, music: Optional[Path] = None, music_volume: float = 0.08) -> None:
    if music and music.exists():
        cmd = [
            "ffmpeg", "-y", "-i", str(video_silent), "-i", str(voice), "-stream_loop", "-1", "-i", str(music),
            "-filter_complex", f"[1:a]volume=1.0[a1];[2:a]volume={music_volume}[a2];[a1][a2]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-shortest", str(out)
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-i", str(video_silent), "-i", str(voice),
            "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest", str(out)
        ]
    run(cmd)


def _escape_subtitle_filter_path(value: str) -> str:
    """Escape a path for FFmpeg's subtitles filter, including Windows drives."""
    escaped = value.replace("\\", "/")
    for character in (":", "'", "[", "]", ",", ";"):
        escaped = escaped.replace(character, "\\" + character)
    return escaped


def _burn_subtitles(video: Path, srt: Path, out: Path, font_size: int = 38, margin_v: int = 70) -> None:
    srt_path = _escape_subtitle_filter_path(str(srt.resolve()))
    style = (
        f"FontName=Arial,FontSize={font_size},PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,MarginV={margin_v}"
    )
    vf = f"subtitles=filename='{srt_path}':force_style='{style}'"
    cmd = ["ffmpeg", "-y", "-i", str(video), "-vf", vf, "-c:a", "copy", str(out)]
    run(cmd)


def _clean_intermediate_outputs(out_root: Path, segments_dir: Path) -> None:
    for segment in segments_dir.glob("segment_*.mp4"):
        if segment.is_file():
            segment.unlink()
    for name in ("segments.txt", "video_silent.mp4", "video_with_audio.mp4", "final_video.new.mp4"):
        candidate = out_root / name
        if candidate.is_file():
            candidate.unlink()


def render_video(
    script_path: str,
    voice_path: str,
    media_dir: str,
    out_dir: str,
    music_path: Optional[str] = None,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    image_duration_seconds: int = 9,
    bitrate: str = "3500k",
    burn_subtitles: bool = False,
    seed: int = 42,
) -> Path:
    if image_duration_seconds <= 0:
        raise ValueError("image_duration_seconds must be greater than zero")
    if width <= 0 or height <= 0 or fps <= 0:
        raise ValueError("width, height, and fps must be greater than zero")

    out_root = Path(out_dir)
    segments_dir = out_root / "segments"
    out_root.mkdir(parents=True, exist_ok=True)
    segments_dir.mkdir(parents=True, exist_ok=True)
    _clean_intermediate_outputs(out_root, segments_dir)

    voice = Path(voice_path).expanduser().resolve()
    if not voice.is_file():
        raise FileNotFoundError(f"Voice file not found: {voice}")
    music = Path(music_path).expanduser().resolve() if music_path else None
    if music and not music.is_file():
        raise FileNotFoundError(f"Background music file not found: {music}")

    subtitle_path = out_root / "subtitles.srt"
    metadata_path = out_root / "metadata.json"
    duration = get_audio_duration(str(voice))
    create_srt_from_script(script_path, str(subtitle_path), target_duration_seconds=duration)
    create_metadata(script_path, str(metadata_path))

    count = max(1, math.ceil(duration / image_duration_seconds))
    per_segment_duration = duration / count
    scene_plan_path = out_root / "scenes.json"
    create_scene_plan(script_path, str(scene_plan_path), target_scenes=min(25, count))
    scene_plan = json.loads(scene_plan_path.read_text(encoding="utf-8"))
    scenes = scene_plan.get("scenes") if isinstance(scene_plan, dict) else []
    scenes = scenes if isinstance(scenes, list) else []
    media_files = choose_media(media_dir, count=count, seed=seed, scenes=scenes)
    scene_slots = distribute_scenes(scenes, count)

    segments: List[Path] = []
    manifest_segments = []
    for idx, src in enumerate(media_files, start=1):
        segment_out = segments_dir / f"segment_{idx:04d}.mp4"
        ext = src.suffix.lower()
        if ext in IMAGE_EXTS:
            _make_image_segment(src, segment_out, per_segment_duration, width, height, fps, bitrate)
        elif ext in VIDEO_EXTS:
            _make_video_segment(src, segment_out, per_segment_duration, width, height, fps, bitrate)
        else:
            continue
        segments.append(segment_out)
        scene = scene_slots[idx - 1] or {}
        manifest_segments.append(
            {
                "segment": idx,
                "scene": scene.get("scene"),
                "keyword": scene.get("keyword"),
                "source": str(src),
                "duration_seconds": round(per_segment_duration, 3),
            }
        )

    silent_video = out_root / "video_silent.mp4"
    with_audio = out_root / "video_with_audio.mp4"
    final_video = out_root / "final_video.mp4"
    final_candidate = out_root / "final_video.new.mp4"

    _concat_segments(segments, silent_video)
    _merge_audio(silent_video, voice, with_audio, music)

    if burn_subtitles:
        _burn_subtitles(with_audio, subtitle_path, final_candidate)
    else:
        with_audio.replace(final_candidate)

    final_candidate.replace(final_video)
    (out_root / "render_manifest.json").write_text(
        json.dumps(
            {
                "audio_duration_seconds": round(duration, 3),
                "segment_count": len(manifest_segments),
                "segments": manifest_segments,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return final_video
