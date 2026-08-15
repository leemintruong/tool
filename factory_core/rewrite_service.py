from __future__ import annotations

import re
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .approval_service import invalidate_approval
from .common import atomic_write_json, atomic_write_text, sha256_file, sha256_text, utc_now_iso
from .gemini_service import GeminiClient, GeminiResult
from .originality_service import validate_script
from .project_manager import ProjectManager


TITLE_RE = re.compile(r"^\s*TITLE\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
SCRIPT_RE = re.compile(r"^\s*SCRIPT\s*:\s*", re.IGNORECASE | re.MULTILINE)


class TextGenerator(Protocol):
    def generate(self, prompt: str) -> GeminiResult: ...


@dataclass
class RewriteOptions:
    projects_root: str | Path = "projects"
    ngram_size: int = 8
    force: bool = False


def _strip_outer_code_fence(text: str) -> str:
    value = text.strip()
    if not value.startswith("```") or not value.endswith("```"):
        return value
    lines = value.splitlines()
    if len(lines) >= 3 and lines[0].lstrip().startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return value


def parse_generated_story(text: str) -> tuple[str | None, str]:
    value = _strip_outer_code_fence(text)
    title_match = TITLE_RE.search(value)
    script_match = SCRIPT_RE.search(value)
    title = title_match.group(1).strip() if title_match else None

    if script_match:
        script = value[script_match.end() :].strip()
    elif title_match:
        script = (value[: title_match.start()] + value[title_match.end() :]).strip()
    else:
        script = value.strip()
    return title, script


def _draft_path(project_dir: Path, result: GeminiResult, suffix: str = "") -> Path:
    stamp = utc_now_iso().replace("+00:00", "Z").replace("-", "").replace(":", "")
    short_hash = sha256_text(result.text)[:10]
    label = f"_{suffix}" if suffix else ""
    return project_dir / "scripts" / "drafts" / f"{stamp}_{short_hash}{label}.txt"


class RewriteService:
    def __init__(self, generator: TextGenerator | None = None, options: RewriteOptions | None = None) -> None:
        self.options = options or RewriteOptions()
        self.generator = generator or GeminiClient()
        self.manager = ProjectManager(self.options.projects_root)

    def rewrite(self, project_reference: str | Path) -> dict[str, Any]:
        project_dir, record = self.manager.load(project_reference)
        prompt_path = project_dir / "prompts" / "rewrite_prompt.txt"
        source_path = project_dir / "transcript" / "transcript_clean.txt"
        rewritten_path = project_dir / "scripts" / "rewritten_script.txt"
        title_path = project_dir / "scripts" / "title.txt"

        if not prompt_path.is_file():
            raise FileNotFoundError(f"Rewrite prompt not found: {prompt_path}")
        if not source_path.is_file():
            raise FileNotFoundError(f"Source transcript not found: {source_path}")

        if rewritten_path.is_file() and not self.options.force:
            if record.get("status") in {"SCRIPT_APPROVED", "BUILDING_VIDEO", "VIDEO_BUILT", "BUILD_FAILED"}:
                return record
            report = validate_script(
                source_path,
                rewritten_path,
                project_dir / "qa",
                ngram_size=self.options.ngram_size,
            )
            return self.manager.set_status(
                project_dir,
                "WAITING_FOR_APPROVAL",
                rewritten_script=str(rewritten_path),
                rewritten_word_count=len(rewritten_path.read_text(encoding="utf-8-sig").split()),
                originality_review_level=report["review_level"],
                originality_overlap_ratio=report["script_overlap_ratio"],
            )

        log_path = project_dir / "logs" / "rewrite.log"
        try:
            self.manager.set_status(project_dir, "REWRITING_WITH_GEMINI", error=None)
            prompt = prompt_path.read_text(encoding="utf-8-sig")
            result = self.generator.generate(prompt)
            if str(result.finish_reason or "STOP").upper() not in {"STOP", "FINISH_REASON_UNSPECIFIED"}:
                partial = _draft_path(project_dir, result, suffix="partial")
                atomic_write_text(partial, result.text.rstrip() + "\n")
                raise RuntimeError(
                    f"Gemini stopped before completing the story ({result.finish_reason}). "
                    f"Partial response saved at: {partial}"
                )

            generated_title, script = parse_generated_story(result.text)
            if not script.strip():
                raise RuntimeError("Gemini returned no usable script text.")

            raw_draft = _draft_path(project_dir, result)
            atomic_write_text(raw_draft, result.text.rstrip() + "\n")

            # A successful new rewrite always invalidates any previous approval.
            invalidate_approval(project_dir)
            atomic_write_text(rewritten_path, script.rstrip() + "\n")
            if generated_title:
                atomic_write_text(title_path, generated_title + "\n")
            else:
                title_path.unlink(missing_ok=True)

            report = validate_script(
                source_path,
                rewritten_path,
                project_dir / "qa",
                ngram_size=self.options.ngram_size,
            )
            manifest = {
                "schema_version": 1,
                "created_at": utc_now_iso(),
                "provider": "gemini",
                "model": result.model,
                "finish_reason": result.finish_reason,
                "response_id": result.response_id,
                "usage": result.usage,
                "prompt_path": str(prompt_path),
                "prompt_sha256": sha256_file(prompt_path),
                "raw_draft": str(raw_draft),
                "generated_title": generated_title,
                "rewritten_script": str(rewritten_path),
                "rewritten_script_sha256": sha256_file(rewritten_path),
                "rewritten_word_count": len(script.split()),
                "originality_review_level": report["review_level"],
                "originality_overlap_ratio": report["script_overlap_ratio"],
            }
            manifest_path = atomic_write_json(project_dir / "qa" / "gemini_rewrite.json", manifest)
            return self.manager.set_status(
                project_dir,
                "WAITING_FOR_APPROVAL",
                approved_script=None,
                approved_script_sha256=None,
                script_approved_at=None,
                rewrite_provider="gemini",
                rewrite_model=result.model,
                generated_title=generated_title,
                rewritten_script=str(rewritten_path),
                rewritten_word_count=manifest["rewritten_word_count"],
                rewrite_manifest=str(manifest_path),
                originality_review_level=report["review_level"],
                originality_overlap_ratio=report["script_overlap_ratio"],
            )
        except Exception as exc:
            atomic_write_text(log_path, traceback.format_exc())
            approved_exists = (project_dir / "scripts" / "approved_script.txt").is_file()
            if approved_exists and record.get("status") in {
                "SCRIPT_APPROVED",
                "BUILDING_VIDEO",
                "VIDEO_BUILT",
                "BUILD_FAILED",
            }:
                self.manager.update(
                    project_dir,
                    status=record.get("status"),
                    last_error=record.get("last_error"),
                    last_rewrite_error=str(exc),
                )
            else:
                self.manager.set_status(project_dir, "REWRITE_FAILED", error=str(exc))
            raise
