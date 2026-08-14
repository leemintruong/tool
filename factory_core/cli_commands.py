from __future__ import annotations

import argparse
import json
from pathlib import Path

from .common import comma_list, load_url_file
from .ingest_service import IngestOptions, IngestService
from .originality_service import validate_script
from .project_manager import ProjectManager
from .prompt_service import build_rewrite_prompt


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
        title = str(record.get("title") or "")
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


def _print_record(record: dict) -> None:
    print("Project result:")
    for key in ("project_id", "title", "status", "transcript_source", "transcript_word_count", "rewrite_prompt"):
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
