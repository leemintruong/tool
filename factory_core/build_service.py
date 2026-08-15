from __future__ import annotations

import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modules.pipeline import build_video_package

from .approval_service import verify_approved_script
from .common import atomic_write_json, atomic_write_text, utc_now_iso
from .project_manager import ProjectManager


@dataclass
class ProjectBuildOptions:
    projects_root: str | Path = "projects"
    media_dir: str | Path = "assets/stock_images"
    out_dir: str | Path | None = None
    voice_path: str | Path | None = None
    tts_model: str | Path | None = None
    piper_bin: str = "piper"
    thumbnail_background: str | Path | None = None
    thumbnail_text: str = "KICKED OUT"
    music_path: str | Path | None = None
    burn_subtitles: bool = False
    width: int = 1920
    height: int = 1080
    fps: int = 30
    image_duration_seconds: int = 9
    bitrate: str = "3500k"
    seed: int = 42


class ProjectBuildService:
    def __init__(self, options: ProjectBuildOptions) -> None:
        self.options = options
        self.manager = ProjectManager(options.projects_root)

    def build(self, project_reference: str | Path) -> dict[str, Any]:
        project_dir, approved_script, approval = verify_approved_script(
            project_reference,
            projects_root=self.options.projects_root,
        )
        media_dir = Path(self.options.media_dir).expanduser().resolve()
        if not media_dir.is_dir():
            raise FileNotFoundError(f"Media directory not found: {media_dir}")
        if not self.options.voice_path and not self.options.tts_model:
            raise ValueError("Provide --voice or --tts-model for build-project.")

        output_dir = (
            Path(self.options.out_dir).expanduser().resolve()
            if self.options.out_dir
            else (project_dir / "output").resolve()
        )
        log_path = project_dir / "logs" / "build.log"
        try:
            self.manager.set_status(project_dir, "BUILDING_VIDEO", error=None)
            result = build_video_package(
                script_path=str(approved_script),
                media_dir=str(media_dir),
                out_dir=str(output_dir),
                voice_path=str(Path(self.options.voice_path).expanduser().resolve()) if self.options.voice_path else None,
                tts_model=str(Path(self.options.tts_model).expanduser().resolve()) if self.options.tts_model else None,
                piper_bin=self.options.piper_bin,
                thumbnail_background=(
                    str(Path(self.options.thumbnail_background).expanduser().resolve())
                    if self.options.thumbnail_background
                    else None
                ),
                thumbnail_text=self.options.thumbnail_text,
                music_path=str(Path(self.options.music_path).expanduser().resolve()) if self.options.music_path else None,
                burn_subtitles=self.options.burn_subtitles,
                width=self.options.width,
                height=self.options.height,
                fps=self.options.fps,
                image_duration_seconds=self.options.image_duration_seconds,
                bitrate=self.options.bitrate,
                seed=self.options.seed,
            )
            build_manifest = {
                "schema_version": 1,
                "built_at": utc_now_iso(),
                "project_id": project_dir.name,
                "approval": approval,
                "approved_script": str(approved_script),
                "media_dir": str(media_dir),
                "output_dir": str(output_dir),
                "outputs": result,
            }
            manifest_path = atomic_write_json(project_dir / "qa" / "project_build.json", build_manifest)
            self.manager.set_status(
                project_dir,
                "VIDEO_BUILT",
                final_video=result.get("final_video"),
                build_manifest=str(manifest_path),
                built_at=build_manifest["built_at"],
            )
            return result
        except Exception as exc:
            atomic_write_text(log_path, traceback.format_exc())
            self.manager.set_status(project_dir, "BUILD_FAILED", error=str(exc))
            raise

