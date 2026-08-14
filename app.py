from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

from factory_core.cli_commands import register_commands as register_v7_commands
from factory_core.common import find_ffmpeg_location, package_status


def cmd_subtitle(args):
    from modules.audio_utils import get_audio_duration
    from modules.subtitle_generator import create_srt_from_script

    target_duration = get_audio_duration(args.audio) if args.audio else None
    out = create_srt_from_script(args.script, args.out, target_duration_seconds=target_duration)
    print(f"Subtitle created: {out}")


def cmd_metadata(args):
    from modules.metadata_generator import create_metadata

    out = create_metadata(args.script, args.out)
    print(f"Metadata created: {out}")


def cmd_tts(args):
    from modules.tts_piper import create_voice_with_piper

    out = create_voice_with_piper(args.script, args.out, args.model, args.piper_bin)
    print(f"Voice created: {out}")


def cmd_plan(args):
    from modules.scene_planner import create_scene_plan

    out = create_scene_plan(args.script, args.out, args.target_scenes)
    print(f"Scene plan created: {out}")


def cmd_build(args):
    from modules.pipeline import build_video_package

    result = build_video_package(
        script_path=args.script,
        media_dir=args.media,
        out_dir=args.out,
        voice_path=args.voice,
        tts_model=args.tts_model,
        piper_bin=args.piper_bin,
        thumbnail_background=args.thumbnail_background,
        thumbnail_text=args.thumbnail_text,
        music_path=args.music,
        burn_subtitles=args.burn_subtitles,
        width=args.width,
        height=args.height,
        fps=args.fps,
        image_duration_seconds=args.image_duration,
        bitrate=args.bitrate,
        seed=args.seed,
    )
    print("Build completed:")
    for key, value in result.items():
        print(f"- {key}: {value}")


def cmd_thumbnail(args):
    from modules.thumbnail_generator import create_thumbnail

    out = create_thumbnail(args.background, args.text, args.out)
    print(f"Thumbnail created: {out}")


def cmd_doctor(_args):
    info: dict[str, str] = {}
    try:
        from modules.env_check import check_environment

        info.update({key: str(value) for key, value in check_environment().items()})
    except Exception as exc:
        info["legacy_env_check"] = f"UNAVAILABLE: {exc}"

    info["ffmpeg_for_yt_dlp"] = find_ffmpeg_location() or "NOT_FOUND"
    info["ffprobe"] = shutil.which("ffprobe") or "NOT_FOUND"
    info["yt_dlp"] = package_status("yt_dlp")
    info["faster_whisper"] = package_status("faster_whisper")
    info["deno"] = shutil.which("deno") or "NOT_FOUND (recommended for current YouTube extraction)"
    info["project_engine"] = "7.1.0"

    print("Environment check:")
    for key, value in info.items():
        print(f"- {key}: {value}")


def cmd_render(args):
    from modules.video_renderer import render_video

    final = render_video(
        script_path=args.script,
        voice_path=args.voice,
        media_dir=args.media,
        out_dir=args.out,
        music_path=args.music,
        width=args.width,
        height=args.height,
        fps=args.fps,
        image_duration_seconds=args.image_duration,
        bitrate=args.bitrate,
        burn_subtitles=args.burn_subtitles,
        seed=args.seed,
    )
    print(f"Final video created: {final}")


def _collect_downloaded_path(data: dict[str, Any], collected: list[str]) -> None:
    if data.get("status") != "finished":
        return
    filename = data.get("filename")
    if filename:
        collected.append(str(Path(filename).resolve()))


def _load_pull_urls(args) -> list[str]:
    urls = list(args.url or [])
    if args.url_file:
        source = Path(args.url_file).expanduser().resolve()
        if not source.is_file():
            raise SystemExit(f"URL file not found: {source}")
        for raw_line in source.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return list(dict.fromkeys(urls))


def cmd_pull(args):
    """Download media that the user has permission to save using yt-dlp."""
    try:
        import yt_dlp
    except ImportError as exc:
        raise SystemExit(
            "Missing yt-dlp. Install it with:\n"
            "  .\\.venv\\Scripts\\python.exe -m pip install -U 'yt-dlp[default]'"
        ) from exc

    output_dir = Path(args.out).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    urls = _load_pull_urls(args)
    if not urls:
        raise SystemExit("Provide at least one --url or use --url-file.")

    downloaded: list[str] = []
    options: dict[str, Any] = {
        "outtmpl": str(output_dir / args.output_template),
        "noplaylist": not args.playlist,
        "overwrites": not args.no_overwrite,
        "continuedl": True,
        "ignoreerrors": False,
        "restrictfilenames": args.restrict_filenames,
        "progress_hooks": [lambda data: _collect_downloaded_path(data, downloaded)],
        "quiet": False,
        "no_warnings": False,
        "retries": args.retries,
        "fragment_retries": args.retries,
        "concurrent_fragment_downloads": args.concurrent_fragments,
    }

    if args.max_downloads is not None:
        options["max_downloads"] = args.max_downloads
    if args.archive:
        archive_path = Path(args.archive).expanduser().resolve()
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        options["download_archive"] = str(archive_path)
    if args.cookies:
        options["cookiefile"] = str(Path(args.cookies).expanduser().resolve())
    if args.cookies_from_browser:
        options["cookiesfrombrowser"] = (args.cookies_from_browser,)

    ffmpeg_location = find_ffmpeg_location()
    if ffmpeg_location:
        options["ffmpeg_location"] = ffmpeg_location
        print(f"FFmpeg selected for yt-dlp: {ffmpeg_location}")
    elif not args.audio_only and "+" in (args.format or "bv*+ba/b"):
        raise SystemExit("FFmpeg was not found for yt-dlp. Run app.py doctor first.")

    if args.audio_only:
        options["format"] = args.format or "bestaudio/best"
        options["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": args.audio_format,
                "preferredquality": args.audio_quality,
            }
        ]
    else:
        options["format"] = args.format or "bv*+ba/b"
        options["merge_output_format"] = args.merge_format

    print(f"Pulling media into: {output_dir}")
    with yt_dlp.YoutubeDL(options) as downloader:
        exit_code = downloader.download(urls)
    if exit_code:
        raise SystemExit(f"yt-dlp exited with code {exit_code}")

    print("Pull completed.")
    if downloaded:
        for path in dict.fromkeys(downloaded):
            print(f"- {path}")
    else:
        print(f"- Check output directory: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="YouTube Auto Factory MVP V7.1")
    sub = parser.add_subparsers(dest="command", required=True)

    parser_doctor = sub.add_parser("doctor", help="Check the local environment")
    parser_doctor.set_defaults(func=cmd_doctor)

    register_v7_commands(sub)

    pull = sub.add_parser("pull", help="Download permitted video/audio media using yt-dlp")
    pull.add_argument("--url", action="append", default=[])
    pull.add_argument("--url-file", default=None)
    pull.add_argument("--out", required=True)
    pull.add_argument("--output-template", default="%(title).120B [%(id)s].%(ext)s")
    pull.add_argument("--format", default=None)
    pull.add_argument("--merge-format", default="mp4", choices=["mp4", "mkv", "webm"])
    pull.add_argument("--playlist", action="store_true")
    pull.add_argument("--max-downloads", type=int, default=None)
    pull.add_argument("--retries", type=int, default=10)
    pull.add_argument("--concurrent-fragments", type=int, default=4)
    pull.add_argument("--archive", default=None)
    pull.add_argument("--cookies", default=None)
    pull.add_argument(
        "--cookies-from-browser",
        choices=["brave", "chrome", "chromium", "edge", "firefox", "opera", "safari", "vivaldi", "whale"],
        default=None,
    )
    pull.add_argument("--no-overwrite", action="store_true")
    pull.add_argument("--restrict-filenames", action="store_true")
    pull.add_argument("--audio-only", action="store_true")
    pull.add_argument("--audio-format", default="mp3", choices=["aac", "alac", "flac", "m4a", "mp3", "opus", "vorbis", "wav"])
    pull.add_argument("--audio-quality", default="192")
    pull.set_defaults(func=cmd_pull)

    plan = sub.add_parser("plan", help="Create scenes.json from script")
    plan.add_argument("--script", required=True)
    plan.add_argument("--out", required=True)
    plan.add_argument("--target-scenes", type=int, default=25)
    plan.set_defaults(func=cmd_plan)

    build = sub.add_parser("build", help="Legacy all-in-one video build")
    build.add_argument("--script", required=True)
    build.add_argument("--media", required=True)
    build.add_argument("--out", required=True)
    build.add_argument("--voice", default=None)
    build.add_argument("--tts-model", default=None)
    build.add_argument("--piper-bin", default="piper")
    build.add_argument("--thumbnail-background", default=None)
    build.add_argument("--thumbnail-text", default="KICKED OUT")
    build.add_argument("--music", default=None)
    build.add_argument("--width", type=int, default=1920)
    build.add_argument("--height", type=int, default=1080)
    build.add_argument("--fps", type=int, default=30)
    build.add_argument("--image-duration", type=int, default=9)
    build.add_argument("--bitrate", default="3500k")
    build.add_argument("--seed", type=int, default=42)
    build.add_argument("--burn-subtitles", action="store_true")
    build.set_defaults(func=cmd_build)

    subtitle = sub.add_parser("subtitle", help="Create .srt from script")
    subtitle.add_argument("--script", required=True)
    subtitle.add_argument("--out", required=True)
    subtitle.add_argument("--audio", default=None, help="Optional voice/audio used to calibrate subtitle timing")
    subtitle.set_defaults(func=cmd_subtitle)

    metadata = sub.add_parser("metadata", help="Create metadata draft JSON")
    metadata.add_argument("--script", required=True)
    metadata.add_argument("--out", required=True)
    metadata.set_defaults(func=cmd_metadata)

    tts = sub.add_parser("tts", help="Create voice.wav using Piper")
    tts.add_argument("--script", required=True)
    tts.add_argument("--out", required=True)
    tts.add_argument("--model", required=True)
    tts.add_argument("--piper-bin", default="piper")
    tts.set_defaults(func=cmd_tts)

    thumbnail = sub.add_parser("thumbnail", help="Create a basic thumbnail draft")
    thumbnail.add_argument("--background", required=True)
    thumbnail.add_argument("--text", required=True)
    thumbnail.add_argument("--out", required=True)
    thumbnail.set_defaults(func=cmd_thumbnail)

    render = sub.add_parser("render", help="Render video from script, voice, and local media")
    render.add_argument("--script", required=True)
    render.add_argument("--voice", required=True)
    render.add_argument("--media", required=True)
    render.add_argument("--out", required=True)
    render.add_argument("--music", default=None)
    render.add_argument("--width", type=int, default=1920)
    render.add_argument("--height", type=int, default=1080)
    render.add_argument("--fps", type=int, default=30)
    render.add_argument("--image-duration", type=int, default=9)
    render.add_argument("--bitrate", default="3500k")
    render.add_argument("--seed", type=int, default=42)
    render.add_argument("--burn-subtitles", action="store_true")
    render.set_defaults(func=cmd_render)

    args = parser.parse_args()
    Path("output").mkdir(exist_ok=True)
    args.func(args)


if __name__ == "__main__":
    main()
