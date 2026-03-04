"""Skills loader — scans workspace for SKILL.md files and injects into prompt.

Skills can come from:
1. Built-in skills: /app/skills/ (shipped with LocalClaw)
2. User workspace: {workspace}/.agents/skills/ or {workspace}/.claude/skills/
   (installed via `npx skills add owner/repo@skill -y`)
"""

import os
from pathlib import Path
from logger import agent_logger


def _parse_frontmatter(content: str) -> dict:
    """Extract YAML-like frontmatter from SKILL.md."""
    if not content.startswith("---"):
        return {}
    end = content.find("---", 3)
    if end == -1:
        return {}
    fm = {}
    for line in content[3:end].split("\n"):
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm


def load_skills(workspace: str) -> str:
    """
    Scan all skills directories and return a table of available skills
    for injection into the system prompt.
    """
    skills_dirs = [
        # Built-in skills shipped with LocalClaw
        str(Path(__file__).parent.parent / "skills"),
        # User-installed via npx skills add
        os.path.join(workspace, ".agents", "skills"),
        os.path.join(workspace, ".claude", "skills"),
        os.path.join(workspace, ".skills"),
    ]

    rows = []
    seen = set()

    for skills_dir in skills_dirs:
        if not os.path.isdir(skills_dir):
            continue
        try:
            for entry in sorted(os.listdir(skills_dir)):
                if entry in seen:
                    continue
                skill_md = os.path.join(skills_dir, entry, "SKILL.md")
                if not os.path.isfile(skill_md):
                    continue
                try:
                    content = open(skill_md, encoding="utf-8").read(3000)
                    fm = _parse_frontmatter(content)
                    description = fm.get("description", "")
                    if not description:
                        # First non-frontmatter non-header line
                        in_fm = content.startswith("---")
                        skip = False
                        for line in content.split("\n"):
                            if line.strip() == "---":
                                skip = not skip
                                continue
                            if skip:
                                continue
                            line = line.strip()
                            if line and not line.startswith("#"):
                                description = line[:150]
                                break
                    rows.append((entry, description[:120], skill_md))
                    seen.add(entry)
                    agent_logger.debug(f"Skill loaded: {entry}")
                except Exception as e:
                    agent_logger.warning(f"Failed to read skill {entry}: {e}")
        except Exception as e:
            agent_logger.warning(f"Skill dir scan failed {skills_dir}: {e}")

    if not rows:
        return "(no skills installed)"

    lines = ["| Skill | Description | Load |"]
    lines.append("|-------|-------------|------|")
    for name, desc, path in rows:
        lines.append(f"| `{name}` | {desc} | `read_file({path})` |")

    lines.append(
        "\nTo find more: `run_command('npx skills find <query>')`"
        "\nTo install: `run_command('npx skills add owner/repo@skill -y')`"
    )
    return "\n".join(lines)
