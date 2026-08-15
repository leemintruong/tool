from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from factory_core.approval_service import ApprovalError, approve_project_script
from factory_core.build_service import ProjectBuildOptions, ProjectBuildService
from factory_core.project_manager import ProjectManager


class BuildServiceTests(unittest.TestCase):
    def _project(self, temp: str) -> tuple[Path, Path]:
        root = Path(temp) / "projects"
        manager = ProjectManager(root)
        manager.create_or_load("https://www.youtube.com/watch?v=Ce3G2LHKkNk")
        project_dir = manager.project_dir("Ce3G2LHKkNk")
        (project_dir / "transcript" / "transcript_clean.txt").write_text(
            "The reference used one sequence of family events in a small town.", encoding="utf-8"
        )
        (project_dir / "scripts" / "rewritten_script.txt").write_text(
            "A new narrator solved a different business dispute in another city.", encoding="utf-8"
        )
        return root, project_dir

    def test_build_requires_approval(self):
        with TemporaryDirectory() as temp:
            root, _project_dir = self._project(temp)
            media = Path(temp) / "media"
            media.mkdir()
            service = ProjectBuildService(
                ProjectBuildOptions(projects_root=root, media_dir=media, voice_path=Path(temp) / "voice.wav")
            )
            with self.assertRaises(ApprovalError):
                service.build("Ce3G2LHKkNk")

    def test_approved_project_uses_approved_copy(self):
        with TemporaryDirectory() as temp:
            root, project_dir = self._project(temp)
            approve_project_script("Ce3G2LHKkNk", projects_root=root)
            media = Path(temp) / "media"
            media.mkdir()
            voice = Path(temp) / "voice.wav"
            voice.touch()
            final = project_dir / "output" / "final_video.mp4"

            with patch(
                "factory_core.build_service.build_video_package",
                return_value={"final_video": str(final)},
            ) as builder:
                result = ProjectBuildService(
                    ProjectBuildOptions(projects_root=root, media_dir=media, voice_path=voice)
                ).build("Ce3G2LHKkNk")

            self.assertEqual(result["final_video"], str(final))
            self.assertTrue(builder.call_args.kwargs["script_path"].endswith("approved_script.txt"))
            self.assertEqual(ProjectManager(root).load("Ce3G2LHKkNk")[1]["status"], "VIDEO_BUILT")


if __name__ == "__main__":
    unittest.main()
