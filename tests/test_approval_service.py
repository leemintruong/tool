from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from factory_core.approval_service import ApprovalError, approve_project_script, verify_approved_script
from factory_core.project_manager import ProjectManager


class ApprovalServiceTests(unittest.TestCase):
    def _project(self, root: Path, project_id: str = "Ce3G2LHKkNk") -> tuple[ProjectManager, Path]:
        manager = ProjectManager(root)
        manager.create_or_load(f"https://www.youtube.com/watch?v={project_id}")
        project_dir = manager.project_dir(project_id)
        (project_dir / "transcript" / "transcript_clean.txt").write_text(
            "A source family argument happened in a coastal town with several specific events.\n",
            encoding="utf-8",
        )
        return manager, project_dir

    def test_approved_script_hash_is_verified(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "projects"
            _manager, project_dir = self._project(root)
            rewritten = project_dir / "scripts" / "rewritten_script.txt"
            rewritten.write_text(
                "A wholly different narrator faced a workplace dispute and resolved it through mediation.\n",
                encoding="utf-8",
            )

            record = approve_project_script("Ce3G2LHKkNk", projects_root=root)
            self.assertEqual(record["status"], "SCRIPT_APPROVED")
            _directory, approved, _manifest = verify_approved_script("Ce3G2LHKkNk", projects_root=root)
            approved.write_text(approved.read_text(encoding="utf-8") + "changed", encoding="utf-8")

            with self.assertRaises(ApprovalError):
                verify_approved_script("Ce3G2LHKkNk", projects_root=root)

    def test_high_overlap_requires_explicit_override(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "projects"
            _manager, project_dir = self._project(root)
            source = (project_dir / "transcript" / "transcript_clean.txt").read_text(encoding="utf-8")
            (project_dir / "scripts" / "rewritten_script.txt").write_text(source, encoding="utf-8")

            with self.assertRaises(ApprovalError):
                approve_project_script("Ce3G2LHKkNk", projects_root=root)

    def test_editing_rewritten_script_invalidates_approval(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "projects"
            _manager, project_dir = self._project(root)
            rewritten = project_dir / "scripts" / "rewritten_script.txt"
            rewritten.write_text(
                "A different narrator resolved a workplace conflict through a carefully documented agreement.\n",
                encoding="utf-8",
            )
            approve_project_script("Ce3G2LHKkNk", projects_root=root)
            rewritten.write_text(rewritten.read_text(encoding="utf-8") + "New edit.\n", encoding="utf-8")

            with self.assertRaises(ApprovalError):
                verify_approved_script("Ce3G2LHKkNk", projects_root=root)

    def test_replacing_source_transcript_invalidates_approval(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "projects"
            _manager, project_dir = self._project(root)
            (project_dir / "scripts" / "rewritten_script.txt").write_text(
                "A different narrator resolved a workplace conflict through a documented agreement.\n",
                encoding="utf-8",
            )
            approve_project_script("Ce3G2LHKkNk", projects_root=root)
            (project_dir / "transcript" / "transcript_clean.txt").write_text(
                "A replacement source transcript with unrelated content.\n", encoding="utf-8"
            )

            with self.assertRaises(ApprovalError):
                verify_approved_script("Ce3G2LHKkNk", projects_root=root)


if __name__ == "__main__":
    unittest.main()
