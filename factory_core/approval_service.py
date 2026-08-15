from __future__ import annotations

from pathlib import Path

from .common import atomic_write_json, atomic_write_text, read_json, sha256_file, utc_now_iso
from .originality_service import validate_script
from .project_manager import ProjectManager


class ApprovalError(RuntimeError):
    pass


def approval_paths(project_dir: str | Path) -> tuple[Path, Path, Path]:
    directory = Path(project_dir)
    return (
        directory / "scripts" / "rewritten_script.txt",
        directory / "scripts" / "approved_script.txt",
        directory / "qa" / "approval.json",
    )


def invalidate_approval(project_dir: str | Path) -> None:
    _rewritten, approved, manifest = approval_paths(project_dir)
    approved.unlink(missing_ok=True)
    manifest.unlink(missing_ok=True)


def approve_project_script(
    project_reference: str | Path,
    *,
    projects_root: str | Path = "projects",
    ngram_size: int = 8,
    allow_high_overlap: bool = False,
) -> dict:
    manager = ProjectManager(projects_root)
    project_dir, _record = manager.load(project_reference)
    rewritten, approved, manifest_path = approval_paths(project_dir)
    source = project_dir / "transcript" / "transcript_clean.txt"

    if not rewritten.is_file():
        raise ApprovalError(f"Rewritten script not found: {rewritten}")
    if not source.is_file():
        raise ApprovalError(f"Source transcript not found: {source}")

    report = validate_script(source, rewritten, project_dir / "qa", ngram_size=ngram_size)
    if report["review_level"] == "HIGH" and not allow_high_overlap:
        raise ApprovalError(
            "Approval blocked because exact phrase overlap is HIGH "
            f"({report['script_overlap_ratio']:.2%}). Edit or rewrite the script first. "
            "If you reviewed it manually and accept the risk, rerun with --allow-high-overlap."
        )

    script_text = rewritten.read_text(encoding="utf-8-sig").strip()
    if not script_text:
        raise ApprovalError("The rewritten script is empty.")
    atomic_write_text(approved, script_text + "\n")

    approved_at = utc_now_iso()
    approved_hash = sha256_file(approved)
    manifest = {
        "schema_version": 1,
        "approved_at": approved_at,
        "project_id": project_dir.name,
        "source_script": str(rewritten),
        "source_script_sha256": sha256_file(rewritten),
        "reference_transcript": str(source),
        "reference_transcript_sha256": sha256_file(source),
        "approved_script": str(approved),
        "approved_script_sha256": approved_hash,
        "originality_review_level": report["review_level"],
        "originality_overlap_ratio": report["script_overlap_ratio"],
        "ngram_size": ngram_size,
    }
    atomic_write_json(manifest_path, manifest)
    return manager.set_status(
        project_dir,
        "SCRIPT_APPROVED",
        approved_script=str(approved),
        approved_script_sha256=approved_hash,
        script_approved_at=approved_at,
        originality_review_level=report["review_level"],
        originality_overlap_ratio=report["script_overlap_ratio"],
    )


def verify_approved_script(
    project_reference: str | Path,
    *,
    projects_root: str | Path = "projects",
) -> tuple[Path, Path, dict]:
    manager = ProjectManager(projects_root)
    project_dir, record = manager.load(project_reference)
    rewritten, approved, manifest_path = approval_paths(project_dir)

    if record.get("status") not in {"SCRIPT_APPROVED", "BUILDING_VIDEO", "VIDEO_BUILT", "BUILD_FAILED"}:
        raise ApprovalError(
            f"Project is not approved (current status: {record.get('status')}). "
            f"Run: app.py approve-script --project {record.get('project_id')}"
        )
    if not approved.is_file() or not manifest_path.is_file():
        raise ApprovalError("Approved script or approval manifest is missing. Approve the project again.")

    manifest = read_json(manifest_path, default={})
    if not isinstance(manifest, dict) or not manifest.get("approved_script_sha256"):
        raise ApprovalError("Approval manifest is invalid. Approve the project again.")
    actual_hash = sha256_file(approved)
    if actual_hash != manifest.get("approved_script_sha256"):
        raise ApprovalError("Approved script changed after approval. Approve the project again before building.")
    if record.get("approved_script_sha256") and actual_hash != record.get("approved_script_sha256"):
        raise ApprovalError("Project approval state does not match the approved script. Approve it again.")
    if rewritten.is_file() and manifest.get("source_script_sha256"):
        if sha256_file(rewritten) != manifest.get("source_script_sha256"):
            raise ApprovalError("Rewritten script changed after approval. Approve the project again before building.")
    source = project_dir / "transcript" / "transcript_clean.txt"
    if source.is_file() and manifest.get("reference_transcript_sha256"):
        if sha256_file(source) != manifest.get("reference_transcript_sha256"):
            raise ApprovalError("Source transcript changed after approval. Review and approve the project again.")
    return project_dir, approved, manifest


def revoke_project_approval(
    project_reference: str | Path,
    *,
    projects_root: str | Path = "projects",
) -> dict:
    manager = ProjectManager(projects_root)
    project_dir, _record = manager.load(project_reference)
    rewritten, _approved, _manifest = approval_paths(project_dir)
    invalidate_approval(project_dir)
    next_status = "WAITING_FOR_APPROVAL" if rewritten.is_file() else "WAITING_FOR_REWRITE"
    return manager.set_status(
        project_dir,
        next_status,
        approved_script=None,
        approved_script_sha256=None,
        script_approved_at=None,
    )
