from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .approval_service import approve_project_script, revoke_project_approval
from .build_service import ProjectBuildOptions, ProjectBuildService
from .common import comma_list, load_url_file
from .gemini_service import GeminiClient, GeminiQuotaError
from .ingest_service import IngestOptions, IngestService
from .originality_service import validate_script
from .project_manager import ProjectManager
from .prompt_service import build_rewrite_prompt
from .rewrite_service import RewriteOptions, RewriteService


def _ingest_options(args: argparse.Namespace) -> IngestOptions:
    return IngestOptions(
        projects_root=args.projects_root,
        languages=tuple(comma_list(args.languages, ["en", "en-US", "en-GB", "vi"])),
        profile_path=args.profile,
        cookies=args.cookies,
        cookies_from_browser=args.cookies_from_browser,
        retries=args.retries,
        audio_fallback=not args.no_audio_fallback,
        auto_transcribe=not args.audio_only_fallback,
        whisper_model=args.whisper_model,
        whisper_language=args.whisper_language,
        whisper_device=args.whisper_device,
        whisper_compute_type=args.whisper_compute_type,
        force=args.force,
    )


def cmd_ingest(args: argparse.Namespace) -> None:
    service = IngestService(_ingest_options(args))
    record = service.ingest(args.url)
    _print_record(record)


def cmd_batch_ingest(args: argparse.Namespace) -> None:
    urls = load_url_file(args.file)
    if not urls:
        raise SystemExit("The URL file contains no usable URLs.")

    service = IngestService(_ingest_options(args))
    successes = 0
    failures = 0
    for index, url in enumerate(urls, start=1):
        print(f"\n=== [{index}/{len(urls)}] {url} ===")
        try:
            record = service.ingest(url)
            _print_record(record)
            successes += 1
        except Exception as exc:
            failures += 1
            print(f"FAILED: {exc}")
            if args.stop_on_error:
                raise

    print("\nBatch completed:")
    print(f"- Success: {successes}")
    print(f"- Failed: {failures}")
    if failures:
        raise SystemExit(2)


def cmd_transcribe_project(args: argparse.Namespace) -> None:
    options = IngestOptions(
        projects_root=args.projects_root,
        profile_path=args.profile,
        whisper_model=args.whisper_model,
        whisper_language=args.whisper_language,
        whisper_device=args.whisper_device,
        whisper_compute_type=args.whisper_compute_type,
    )
    record = IngestService(options).transcribe_existing(args.project)
    _print_record(record)


def cmd_make_prompt(args: argparse.Namespace) -> None:
    manager = ProjectManager(args.projects_root)
    project_dir, record = manager.load(args.project)
    output = build_rewrite_prompt(project_dir, profile_path=args.profile)
    manager.update(project_dir, rewrite_prompt=str(output))
    print(f"Rewrite prompt created: {output}")


def cmd_project_status(args: argparse.Namespace) -> None:
    manager = ProjectManager(args.projects_root)
    project_dir, record = manager.load(args.project)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    print(f"Project directory: {project_dir}")


def cmd_list_projects(args: argparse.Namespace) -> None:
    projects = ProjectManager(args.projects_root).list_projects()
    if not projects:
        print(f"No projects found in: {Path(args.projects_root).resolve()}")
        return
    print(f"{'PROJECT':<16} {'STATUS':<32} TITLE")
    print("-" * 100)
    for record in projects:
        title = str(record.get("generated_title") or record.get("title") or "")
        print(f"{str(record.get('project_id')):<16} {str(record.get('status')):<32} {title[:50]}")


def cmd_validate_script(args: argparse.Namespace) -> None:
    manager = ProjectManager(args.projects_root)
    project_dir, _record = manager.load(args.project)
    source = project_dir / "transcript" / "transcript_clean.txt"
    script = Path(args.script).expanduser().resolve() if args.script else project_dir / "scripts" / "rewritten_script.txt"
    if not source.is_file():
        raise FileNotFoundError(f"Source transcript not found: {source}")
    if not script.is_file():
        raise FileNotFoundError(
            f"Rewritten script not found: {script}\n"
            "Save the AI result as scripts/rewritten_script.txt or pass --script."
        )
    report = validate_script(source, script, project_dir / "qa", ngram_size=args.ngram_size)
    print(f"Review level: {report['review_level']}")
    print(f"Exact {args.ngram_size}-word overlap: {report['script_overlap_ratio']:.2%}")
    print(f"Report: {report['text_path']}")


def _gemini_client(args: argparse.Namespace) -> GeminiClient:
    return GeminiClient(
        model=args.model,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
        retries=args.gemini_retries,
        timeout_seconds=args.timeout_seconds,
    )


def cmd_rewrite(args: argparse.Namespace) -> None:
    service = RewriteService(
        _gemini_client(args),
        RewriteOptions(
            projects_root=args.projects_root,
            ngram_size=args.ngram_size,
            force=args.force,
        ),
    )
    record = service.rewrite(args.project)
    _print_record(record)


def cmd_batch_rewrite(args: argparse.Namespace) -> None:
    manager = ProjectManager(args.projects_root)
    if args.project:
        records = [manager.load(project)[1] for project in dict.fromkeys(args.project)]
    else:
        eligible = {"WAITING_FOR_REWRITE", "REWRITE_FAILED"}
        if args.force:
            eligible.add("WAITING_FOR_APPROVAL")
        records = [record for record in manager.list_projects() if record.get("status") in eligible]

    if args.limit is not None:
        records = records[: args.limit]
    if not records:
        print("No projects are waiting for Gemini rewrite.")
        return

    service = RewriteService(
        _gemini_client(args),
        RewriteOptions(
            projects_root=args.projects_root,
            ngram_size=args.ngram_size,
            force=args.force,
        ),
    )
    successes = 0
    failures = 0
    total = len(records)
    for index, record in enumerate(records, start=1):
        project_id = str(record.get("project_id"))
        print(f"\n=== Gemini rewrite [{index}/{total}] {project_id} ===")
        try:
            updated = service.rewrite(project_id)
            _print_record(updated)
            successes += 1
        except GeminiQuotaError as exc:
            failures += 1
            print(f"FREE TIER STOPPED: {exc}")
            print("Remaining projects were left unchanged so the batch can be resumed later.")
            break
        except Exception as exc:
            failures += 1
            print(f"FAILED: {exc}")
            if args.stop_on_error:
                raise
        if index < total and args.delay_seconds > 0:
            print(f"Waiting {args.delay_seconds:g}s before the next Free Tier request...")
            time.sleep(args.delay_seconds)

    print("\nBatch rewrite completed:")
    print(f"- Success: {successes}")
    print(f"- Failed: {failures}")
    print("- No project was approved or rendered automatically.")
    if failures:
        raise SystemExit(2)


def cmd_approve_script(args: argparse.Namespace) -> None:
    record = approve_project_script(
        args.project,
        projects_root=args.projects_root,
        ngram_size=args.ngram_size,
        allow_high_overlap=args.allow_high_overlap,
    )
    print(f"Project approved: {record.get('project_id')}")
    print(f"Approved script: {record.get('approved_script')}")
    print(f"Originality review: {record.get('originality_review_level')}")


def cmd_revoke_approval(args: argparse.Namespace) -> None:
    record = revoke_project_approval(args.project, projects_root=args.projects_root)
    print(f"Approval revoked: {record.get('project_id')}")
    print(f"Status: {record.get('status')}")


def cmd_build_project(args: argparse.Namespace) -> None:
    service = ProjectBuildService(
        ProjectBuildOptions(
            projects_root=args.projects_root,
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
    )
    result = service.build(args.project)
    print("Approved project build completed:")
    for key, value in result.items():
        print(f"- {key}: {value}")


def _print_record(record: dict) -> None:
    print("Project result:")
    for key in (
        "project_id",
        "title",
        "status",
        "transcript_source",
        "transcript_word_count",
        "rewrite_prompt",
        "rewrite_model",
        "generated_title",
        "rewritten_script",
        "rewritten_word_count",
        "originality_review_level",
        "approved_script",
        "final_video",
    ):
        if record.get(key) is not None:
            print(f"- {key}: {record.get(key)}")


def _add_common_ingest_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--projects-root", default="projects")
    parser.add_argument("--languages", default="en,en-US,en-GB,vi", help="Preferred subtitle languages, comma separated")
    parser.add_argument("--profile", default="config/profiles/family_drama_us.yaml")
    parser.add_argument("--cookies", default=None, help="Netscape cookies.txt path")
    parser.add_argument(
        "--cookies-from-browser",
        choices=["brave", "chrome", "chromium", "edge", "firefox", "opera", "safari", "vivaldi", "whale"],
        default=None,
    )
    parser.add_argument("--retries", type=int, default=10)
    parser.add_argument("--no-audio-fallback", action="store_true", help="Do not download audio when no subtitle exists")
    parser.add_argument("--audio-only-fallback", action="store_true", help="Download fallback audio but do not run Whisper automatically")
    parser.add_argument("--whisper-model", default="small")
    parser.add_argument("--whisper-language", default=None)
    parser.add_argument("--whisper-device", default="cpu", choices=["cpu", "cuda", "auto"])
    parser.add_argument("--whisper-compute-type", default="int8")
    parser.add_argument("--force", action="store_true", help="Re-run ingest even when transcript_clean.txt already exists")


def _add_gemini_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", default=None, help="Gemini model; default is GEMINI_MODEL or gemini-3.1-flash-lite")
    parser.add_argument("--temperature", type=float, default=0.85)
    parser.add_argument("--max-output-tokens", type=int, default=32768)
    parser.add_argument("--gemini-retries", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--ngram-size", type=int, default=8)
    parser.add_argument("--force", action="store_true", help="Replace an existing rewrite and invalidate its approval")


def register_commands(subparsers) -> None:
    parser = subparsers.add_parser(
        "ingest",
        help="Create a project from a YouTube URL and export clean transcript TXT + AI rewrite prompt",
    )
    parser.add_argument("--url", required=True)
    _add_common_ingest_arguments(parser)
    parser.set_defaults(func=cmd_ingest)

    parser = subparsers.add_parser("batch-ingest", help="Ingest multiple YouTube URLs from a UTF-8 text file")
    parser.add_argument("--file", required=True)
    parser.add_argument("--stop-on-error", action="store_true")
    _add_common_ingest_arguments(parser)
    parser.set_defaults(func=cmd_batch_ingest)

    parser = subparsers.add_parser("transcribe-project", help="Transcribe previously downloaded reference audio using faster-whisper")
    parser.add_argument("--project", required=True)
    parser.add_argument("--projects-root", default="projects")
    parser.add_argument("--profile", default="config/profiles/family_drama_us.yaml")
    parser.add_argument("--whisper-model", default="small")
    parser.add_argument("--whisper-language", default=None)
    parser.add_argument("--whisper-device", default="cpu", choices=["cpu", "cuda", "auto"])
    parser.add_argument("--whisper-compute-type", default="int8")
    parser.set_defaults(func=cmd_transcribe_project)

    parser = subparsers.add_parser("make-prompt", help="Regenerate prompts/rewrite_prompt.txt for a project")
    parser.add_argument("--project", required=True)
    parser.add_argument("--projects-root", default="projects")
    parser.add_argument("--profile", default="config/profiles/family_drama_us.yaml")
    parser.set_defaults(func=cmd_make_prompt)

    parser = subparsers.add_parser("project-status", help="Show one project's JSON state")
    parser.add_argument("--project", required=True)
    parser.add_argument("--projects-root", default="projects")
    parser.set_defaults(func=cmd_project_status)

    parser = subparsers.add_parser("list-projects", help="List all projects and their pipeline states")
    parser.add_argument("--projects-root", default="projects")
    parser.set_defaults(func=cmd_list_projects)

    parser = subparsers.add_parser("validate-script", help="Check exact phrase overlap between source and rewritten script")
    parser.add_argument("--project", required=True)
    parser.add_argument("--projects-root", default="projects")
    parser.add_argument("--script", default=None)
    parser.add_argument("--ngram-size", type=int, default=8)
    parser.set_defaults(func=cmd_validate_script)

    parser = subparsers.add_parser("rewrite", help="Rewrite one project with Gemini Free; never approves or renders")
    parser.add_argument("--project", required=True)
    parser.add_argument("--projects-root", default="projects")
    _add_gemini_arguments(parser)
    parser.set_defaults(func=cmd_rewrite)

    parser = subparsers.add_parser("batch-rewrite", help="Sequentially rewrite multiple projects with Gemini Free")
    parser.add_argument("--project", action="append", default=[], help="Optional project ID; repeat for multiple projects")
    parser.add_argument("--projects-root", default="projects")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay-seconds", type=float, default=10.0)
    parser.add_argument("--stop-on-error", action="store_true")
    _add_gemini_arguments(parser)
    parser.set_defaults(func=cmd_batch_rewrite)

    parser = subparsers.add_parser("approve-script", help="Manually approve a rewritten script before project build")
    parser.add_argument("--project", required=True)
    parser.add_argument("--projects-root", default="projects")
    parser.add_argument("--ngram-size", type=int, default=8)
    parser.add_argument("--allow-high-overlap", action="store_true")
    parser.set_defaults(func=cmd_approve_script)

    parser = subparsers.add_parser("revoke-approval", help="Invalidate a project's prior script approval")
    parser.add_argument("--project", required=True)
    parser.add_argument("--projects-root", default="projects")
    parser.set_defaults(func=cmd_revoke_approval)

    parser = subparsers.add_parser("build-project", help="Build only from a verified approved_script.txt")
    parser.add_argument("--project", required=True)
    parser.add_argument("--projects-root", default="projects")
    parser.add_argument("--media", required=True)
    parser.add_argument("--out", default=None)
    parser.add_argument("--voice", default=None)
    parser.add_argument("--tts-model", default=None)
    parser.add_argument("--piper-bin", default="piper")
    parser.add_argument("--thumbnail-background", default=None)
    parser.add_argument("--thumbnail-text", default="KICKED OUT")
    parser.add_argument("--music", default=None)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--image-duration", type=int, default=9)
    parser.add_argument("--bitrate", default="3500k")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--burn-subtitles", action="store_true")
    parser.set_defaults(func=cmd_build_project)
