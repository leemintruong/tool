from __future__ import annotations

import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import atomic_write_json, atomic_write_text
from .project_manager import ProjectManager
from .prompt_service import build_rewrite_prompt
from .transcript_service import parse_subtitle, write_transcript_outputs
from .transcription_service import faster_whisper_available, transcribe_audio
from .youtube_service import (
    choose_subtitle,
    download_audio,
    download_subtitle,
    extract_metadata,
    write_metadata,
)


@dataclass
class IngestOptions:
    projects_root: str | Path = "projects"
    languages: tuple[str, ...] = ("en", "en-US", "en-GB", "vi")
    profile_path: str | Path = "config/profiles/family_drama_us.yaml"
    cookies: str | None = None
    cookies_from_browser: str | None = None
    retries: int = 10
    audio_fallback: bool = True
    auto_transcribe: bool = True
    whisper_model: str = "small"
    whisper_language: str | None = None
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    force: bool = False


class IngestService:
    def __init__(self, options: IngestOptions) -> None:
        self.options = options
        self.manager = ProjectManager(options.projects_root)

    def ingest(self, url: str) -> dict[str, Any]:
        record = self.manager.create_or_load(url)
        project_dir = self.manager.project_dir(record["project_id"])
        clean_transcript = project_dir / "transcript" / "transcript_clean.txt"

        if clean_transcript.is_file() and not self.options.force:
            print(f"Project already has a transcript; skipping ingest: {project_dir}")
            return self.manager.update(project_dir, last_error=None)

        log_path = project_dir / "logs" / "ingest.log"
        try:
            self.manager.set_status(project_dir, "INGESTING_METADATA")
            info = extract_metadata(
                url,
                cookies=self.options.cookies,
                cookies_from_browser=self.options.cookies_from_browser,
                retries=self.options.retries,
            )
            write_metadata(project_dir / "source" / "metadata.json", info)
            record = self.manager.update(
                project_dir,
                title=info.get("title"),
                video_id=info.get("id") or record.get("video_id"),
                source_url=info.get("webpage_url") or url,
            )

            choice = choose_subtitle(info, list(self.options.languages))
            if choice:
                self.manager.set_status(project_dir, "DOWNLOADING_SUBTITLE")
                subtitle_path = download_subtitle(
                    url,
                    project_dir / "source",
                    choice,
                    cookies=self.options.cookies,
                    cookies_from_browser=self.options.cookies_from_browser,
                    retries=self.options.retries,
                )
                segments = parse_subtitle(subtitle_path)
                if not segments:
                    raise RuntimeError(f"Subtitle file contained no usable text: {subtitle_path}")
                outputs = write_transcript_outputs(
                    project_dir,
                    segments,
                    source_kind=f"youtube_{choice.kind}",
                    source_file=subtitle_path,
                )
                prompt_path = build_rewrite_prompt(project_dir, profile_path=self.options.profile_path)
                record = self.manager.set_status(
                    project_dir,
                    "WAITING_FOR_REWRITE",
                    transcript_source=f"youtube_{choice.kind}:{choice.language}",
                    transcript_word_count=outputs["word_count"],
                    rewrite_prompt=str(prompt_path),
                )
                self._write_summary(project_dir, record, outputs)
                return record

            if not self.options.audio_fallback:
                record = self.manager.set_status(
                    project_dir,
                    "NO_TRANSCRIPT_AVAILABLE",
                    transcript_source=None,
                )
                atomic_write_text(
                    project_dir / "NEXT_STEP.txt",
                    "No YouTube subtitle was available and audio fallback was disabled.\n",
                )
                return record

            self.manager.set_status(project_dir, "DOWNLOADING_REFERENCE_AUDIO")
            audio_path = download_audio(
                url,
                project_dir / "source",
                cookies=self.options.cookies,
                cookies_from_browser=self.options.cookies_from_browser,
                retries=self.options.retries,
            )

            if not self.options.auto_transcribe or not faster_whisper_available():
                next_step = (
                    "Reference audio is ready, but local transcription is not installed.\n\n"
                    "Run INSTALL_WHISPER_WINDOWS.bat, then run:\n"
                    f".\\.venv\\Scripts\\python.exe .\\app.py transcribe-project --project {record['project_id']}\n"
                )
                atomic_write_text(project_dir / "NEXT_STEP.txt", next_step)
                return self.manager.set_status(
                    project_dir,
                    "AUDIO_READY_WHISPER_REQUIRED",
                    transcript_source=None,
                    reference_audio=str(audio_path),
                )

            return self._transcribe(project_dir, record, audio_path)
        except Exception as exc:
            details = traceback.format_exc()
            atomic_write_text(log_path, details)
            self.manager.set_status(project_dir, "FAILED", error=str(exc))
            raise

    def transcribe_existing(self, project_reference: str | Path) -> dict[str, Any]:
        project_dir, record = self.manager.load(project_reference)
        candidates = sorted((project_dir / "source").glob("reference_audio.*"))
        if not candidates:
            raise FileNotFoundError(f"Reference audio not found in: {project_dir / 'source'}")
        return self._transcribe(project_dir, record, candidates[0])

    def _transcribe(self, project_dir: Path, record: dict, audio_path: Path) -> dict[str, Any]:
        self.manager.set_status(project_dir, "TRANSCRIBING_AUDIO")
        segments, whisper_info = transcribe_audio(
            audio_path,
            model_name=self.options.whisper_model,
            language=self.options.whisper_language,
            device=self.options.whisper_device,
            compute_type=self.options.whisper_compute_type,
        )
        if not segments:
            raise RuntimeError("Whisper produced no transcript segments.")
        atomic_write_json(project_dir / "source" / "whisper_info.json", whisper_info)
        outputs = write_transcript_outputs(
            project_dir,
            segments,
            source_kind="faster_whisper",
            source_file=audio_path,
        )
        prompt_path = build_rewrite_prompt(project_dir, profile_path=self.options.profile_path)
        record = self.manager.set_status(
            project_dir,
            "WAITING_FOR_REWRITE",
            transcript_source=f"faster_whisper:{self.options.whisper_model}",
            transcript_word_count=outputs["word_count"],
            rewrite_prompt=str(prompt_path),
        )
        self._write_summary(project_dir, record, outputs)
        return record

    @staticmethod
    def _write_summary(project_dir: Path, record: dict, outputs: dict) -> None:
        text = (
            "INGEST COMPLETED\n"
            "================\n"
            f"Project: {record.get('project_id')}\n"
            f"Title: {record.get('title')}\n"
            f"Status: {record.get('status')}\n"
            f"Transcript source: {record.get('transcript_source')}\n"
            f"Transcript words: {outputs.get('word_count')}\n\n"
            "Next file to use:\n"
            "prompts/rewrite_prompt.txt\n\n"
            "Automatic Gemini next step:\n"
            f".\\.venv\\Scripts\\python.exe .\\app.py rewrite --project {record.get('project_id')}\n"
        )
        atomic_write_text(project_dir / "INGEST_RESULT.txt", text)
