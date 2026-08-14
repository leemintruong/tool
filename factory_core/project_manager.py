from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .common import atomic_write_json, read_json, utc_now_iso

PROJECT_FOLDERS = (
    "source",
    "transcript",
    "prompts",
    "scripts",
    "voice",
    "scenes",
    "assets/generated_images",
    "assets/licensed_stock",
    "qa",
    "preview",
    "output",
    "logs",
)

YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_youtube_id(url: str) -> str | None:
    value = url.strip()
    if YOUTUBE_ID_RE.fullmatch(value):
        return value

    parsed = urlparse(value)
    host = parsed.netloc.lower().split(":", 1)[0]
    host = host.removeprefix("www.").removeprefix("m.")

    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/", 1)[0]
        return candidate if YOUTUBE_ID_RE.fullmatch(candidate) else None

    if host.endswith("youtube.com"):
        query_id = parse_qs(parsed.query).get("v", [None])[0]
        if query_id and YOUTUBE_ID_RE.fullmatch(query_id):
            return query_id

        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0].lower() in {"shorts", "embed", "live", "v"}:
            candidate = parts[1]
            return candidate if YOUTUBE_ID_RE.fullmatch(candidate) else None
    return None


def project_id_for_url(url: str) -> str:
    video_id = extract_youtube_id(url)
    if video_id:
        return video_id
    return "url_" + hashlib.sha1(url.strip().encode("utf-8")).hexdigest()[:12]


class ProjectManager:
    def __init__(self, root: str | Path = "projects") -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def project_dir(self, project_id: str) -> Path:
        return self.root / project_id

    def create_or_load(self, source_url: str, project_id: str | None = None) -> dict:
        resolved_id = project_id or project_id_for_url(source_url)
        project_dir = self.project_dir(resolved_id)
        for relative in PROJECT_FOLDERS:
            (project_dir / relative).mkdir(parents=True, exist_ok=True)

        record_path = project_dir / "project.json"
        record = read_json(record_path, default=None)
        if not isinstance(record, dict):
            now = utc_now_iso()
            record = {
                "schema_version": 1,
                "project_id": resolved_id,
                "source_url": source_url,
                "video_id": extract_youtube_id(source_url),
                "title": None,
                "status": "PENDING",
                "created_at": now,
                "updated_at": now,
                "transcript_source": None,
                "last_error": None,
                "paths": {
                    "project_dir": str(project_dir),
                    "metadata": "source/metadata.json",
                    "transcript_clean": "transcript/transcript_clean.txt",
                    "rewrite_prompt": "prompts/rewrite_prompt.txt",
                    "approved_script": "scripts/approved_script.txt",
                    "final_video": "output/final_video.mp4",
                },
            }
            atomic_write_json(record_path, record)
        return record

    def load(self, reference: str | Path) -> tuple[Path, dict]:
        candidate = Path(reference).expanduser()
        if candidate.exists():
            project_dir = candidate.resolve()
        else:
            project_dir = self.project_dir(str(reference))

        record_path = project_dir / "project.json"
        record = read_json(record_path, default=None)
        if not isinstance(record, dict):
            raise FileNotFoundError(f"Project not found or invalid: {project_dir}")
        return project_dir, record

    def update(self, project_dir: str | Path, **changes) -> dict:
        directory = Path(project_dir)
        path = directory / "project.json"
        record = read_json(path, default={})
        record.update(changes)
        record["updated_at"] = utc_now_iso()
        atomic_write_json(path, record)
        return record

    def set_status(self, project_dir: str | Path, status: str, error: str | None = None, **changes) -> dict:
        return self.update(project_dir, status=status, last_error=error, **changes)

    def list_projects(self) -> list[dict]:
        projects: list[dict] = []
        for path in sorted(self.root.glob("*/project.json")):
            record = read_json(path, default=None)
            if isinstance(record, dict):
                projects.append(record)
        return sorted(projects, key=lambda item: item.get("updated_at") or "", reverse=True)
