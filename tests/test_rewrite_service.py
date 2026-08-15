from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from factory_core.gemini_service import GeminiResult
from factory_core.project_manager import ProjectManager
from factory_core.rewrite_service import RewriteOptions, RewriteService


class FakeGenerator:
    def __init__(self):
        self.calls = 0

    def generate(self, _prompt: str) -> GeminiResult:
        self.calls += 1
        return GeminiResult(
            text="TITLE: The New Boundary\nSCRIPT:\nMara returned to Denver and handled an entirely new conflict.",
            model="gemini-test",
            finish_reason="STOP",
            usage={"promptTokenCount": 50, "candidatesTokenCount": 25},
            response_id="test-response",
        )


class RewriteServiceTests(unittest.TestCase):
    def test_rewrite_saves_script_report_and_waits_for_approval(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "projects"
            manager = ProjectManager(root)
            manager.create_or_load("https://www.youtube.com/watch?v=Ce3G2LHKkNk")
            project_dir = manager.project_dir("Ce3G2LHKkNk")
            (project_dir / "transcript" / "transcript_clean.txt").write_text(
                "The reference followed another family in Seattle through a property disagreement.",
                encoding="utf-8",
            )
            (project_dir / "prompts" / "rewrite_prompt.txt").write_text(
                "Write a materially different story.",
                encoding="utf-8",
            )
            (project_dir / "scripts" / "approved_script.txt").write_text("old approval", encoding="utf-8")
            (project_dir / "qa" / "approval.json").write_text("{}", encoding="utf-8")

            generator = FakeGenerator()
            record = RewriteService(
                generator,
                RewriteOptions(projects_root=root, force=True),
            ).rewrite("Ce3G2LHKkNk")

            self.assertEqual(record["status"], "WAITING_FOR_APPROVAL")
            self.assertEqual(record["generated_title"], "The New Boundary")
            self.assertEqual(generator.calls, 1)
            self.assertEqual(
                (project_dir / "scripts" / "rewritten_script.txt").read_text(encoding="utf-8").strip(),
                "Mara returned to Denver and handled an entirely new conflict.",
            )
            self.assertFalse((project_dir / "scripts" / "approved_script.txt").exists())
            self.assertTrue((project_dir / "qa" / "gemini_rewrite.json").is_file())
            self.assertTrue(list((project_dir / "scripts" / "drafts").glob("*.txt")))


if __name__ == "__main__":
    unittest.main()
