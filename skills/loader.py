from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Skill:
    name: str
    description: str
    body: str
    file_path: Path


def load_skills(skills_dir: str | Path = "skills") -> list[Skill]:
    """Glob all .md files in skills_dir, parse YAML frontmatter, return Skill objects."""
    skills_dir = Path(skills_dir)
    skills = []
    for md_file in sorted(skills_dir.glob("*.md")):
        text = md_file.read_text()
        # Parse YAML frontmatter between --- markers
        if not text.startswith("---"):
            continue
        end = text.index("---", 3)
        frontmatter = yaml.safe_load(text[3:end])
        body = text[end + 3 :].strip()

        skills.append(
            Skill(
                name=frontmatter["name"],
                description=frontmatter["description"],
                body=body,
                file_path=md_file,
            )
        )
    return skills
