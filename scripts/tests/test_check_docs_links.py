import subprocess
import tempfile
import unittest
from pathlib import Path

CHECKER = Path(__file__).resolve().parents[1] / "check_docs_links.py"


class MarkdownLinkCheckerTests(unittest.TestCase):
    def run_checker(self, root: Path, *paths: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(CHECKER), "--root", str(root), *paths],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_accepts_local_links_and_ignores_external_mail_and_anchor_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "asset.svg").write_text("<svg/>", encoding="utf-8")
            (root / "docs" / "guide.md").write_text(
                "[asset](../asset.svg)\n"
                "[web](https://example.com) [mail](mailto:test@example.com) [section](#part)\n",
                encoding="utf-8",
            )

            result = self.run_checker(root, "docs/guide.md")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("1 local link", result.stdout)

    def test_reports_missing_link_with_file_and_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "docs" / "guide.md").write_text("[missing](nope.md)\n", encoding="utf-8")

            result = self.run_checker(root, "docs/guide.md")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing local link", result.stderr)
            self.assertIn("docs/guide.md:1", result.stderr)

    def test_parses_balanced_and_escaped_parentheses_around_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "assets").mkdir()
            (root / "assets" / "diagram_(v2_(draft)).svg").write_text("<svg/>", encoding="utf-8")
            (root / "assets" / "escaped(name).svg").write_text("<svg/>", encoding="utf-8")
            (root / "docs" / "guide.md").write_text(
                "[nested](../assets/diagram_(v2_(draft)).svg)\n"
                "[escaped](../assets/escaped\\(name\\).svg)\n"
                "``code ` [ignored](missing-code.md)``\n"
                "````markdown\n"
                "[ignored](missing-fence-one.md)\n"
                "```\n"
                "[still ignored](missing-fence-two.md)\n"
                "````\n",
                encoding="utf-8",
            )

            result = self.run_checker(root, "docs/guide.md")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("2 local links", result.stdout)

    def test_rejects_parent_directory_escape_even_when_target_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "repo"
            (root / "docs").mkdir(parents=True)
            (base / "outside.md").write_text("outside", encoding="utf-8")
            (root / "docs" / "guide.md").write_text(
                "[outside](../../outside.md)\n", encoding="utf-8"
            )

            result = self.run_checker(root, "docs/guide.md")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("escapes repository root", result.stderr)
            self.assertIn("docs/guide.md:1", result.stderr)

    def test_rejects_symlink_escape_even_when_target_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "repo"
            outside = base / "outside"
            (root / "docs").mkdir(parents=True)
            outside.mkdir()
            (outside / "secret.md").write_text("secret", encoding="utf-8")
            (root / "docs" / "escape").symlink_to(outside, target_is_directory=True)
            (root / "docs" / "guide.md").write_text(
                "[secret](escape/secret.md)\n", encoding="utf-8"
            )

            result = self.run_checker(root, "docs/guide.md")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("escapes repository root", result.stderr)
            self.assertIn("docs/guide.md:1", result.stderr)


if __name__ == "__main__":
    unittest.main()
