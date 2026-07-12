from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class AgentsAndSkillsTest(unittest.TestCase):
    def test_agent_skill_references_exist(self) -> None:
        for path in sorted((ROOT / "agents").glob("*.yaml")):
            agent = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(1, agent["version"], path)
            self.assertEqual(path.stem, agent["name"], path)
            for skill in agent["skills"]:
                self.assertTrue((ROOT / "skills" / skill / "SKILL.md").is_file(), f"{path}: missing {skill}")
            for workflow in agent.get("default_workflows", []):
                self.assertTrue((ROOT / workflow).is_file(), f"{path}: missing {workflow}")

    def test_skills_have_no_template_markers(self) -> None:
        for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("TODO", text, path)
            self.assertIn("description:", text, path)


if __name__ == "__main__":
    unittest.main()

