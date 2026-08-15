from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app import _guard_project_script_approval
from factory_core.approval_service import approve_project_script
from factory_core.project_manager import ProjectManager


class LegacyApprovalGuardTests(unittest.TestCase):
    def test_project_render_path_cannot_bypass_approval(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "projects"
            manager = ProjectManager(root)
            manager.create_or_load("https://www.youtube.com/watch?v=Ce3G2LHKkNk")
            project_dir = manager.project_dir("Ce3G2LHKkNk")
            source = project_dir / "transcript" / "transcript_clean.txt"
            rewritten = project_dir / "scripts" / "rewritten_script.txt"
            source.write_text("A reference family dispute happened in Seattle.", encoding="utf-8")
            rewritten.write_text("A new workplace story happened in Denver.", encoding="utf-8")

            with self.assertRaises(SystemExit):
                _guard_project_script_approval(str(rewritten))

            approve_project_script("Ce3G2LHKkNk", projects_root=root)
            approved = project_dir / "scripts" / "approved_script.txt"
            _guard_project_script_approval(str(approved))
            with self.assertRaises(SystemExit):
                _guard_project_script_approval(str(rewritten))


if __name__ == "__main__":
    unittest.main()
