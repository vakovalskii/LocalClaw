"""search_tools — find available tools and skills by keyword.

This is the agent's discovery mechanism:
  search_tools(query="docker") → returns list of tools matching "docker"
  search_tools(query="pptx") → returns matching skills

Searches across:
  - Built-in tools
  - MCP tools (if servers running)
  - Installed skills (SKILL.md scan)
"""

import os
from pathlib import Path
from models import ToolResult, ToolContext
from logger import tool_logger


async def tool_search_tools(args: dict, ctx: ToolContext) -> ToolResult:
    query = args.get("query", "").strip().lower()
    if not query:
        return ToolResult(False, error="query is required")

    results = []

    # 1. Built-in tools
    from tools import _DEFINITIONS as builtin_defs
    for t in builtin_defs:
        fn = t.get("function", {})
        name = fn.get("name", "")
        desc = fn.get("description", "")
        if query in name.lower() or query in desc.lower():
            results.append(f"[builtin] {name} — {desc[:100]}")

    # 2. MCP tools
    try:
        from tools.mcp import mcp_manager
        for t in mcp_manager.get_all_tools():
            fn = t.get("function", {})
            name = fn.get("name", "")
            desc = fn.get("description", "")
            if query in name.lower() or query in desc.lower():
                source = t.get("source", "mcp")
                results.append(f"[{source}] {name} — {desc[:100]}")
    except Exception as e:
        tool_logger.debug(f"MCP search skip: {e}")

    # 3. Installed skills (SKILL.md scan)
    from config import CONFIG
    skills_dirs = [
        str(Path(__file__).parent.parent / "skills"),
        os.path.join(CONFIG.workspace, ".agents", "skills"),
        os.path.join(CONFIG.workspace, ".claude", "skills"),
    ]
    for skills_dir in skills_dirs:
        if not os.path.isdir(skills_dir):
            continue
        for entry in os.listdir(skills_dir):
            if query not in entry.lower():
                continue
            skill_md = os.path.join(skills_dir, entry, "SKILL.md")
            desc = ""
            if os.path.isfile(skill_md):
                try:
                    content = open(skill_md).read(500)
                    for line in content.split("\n"):
                        if line.strip().startswith("description:"):
                            desc = line.split(":", 1)[1].strip().strip('"').strip("'")[:100]
                            break
                except Exception:
                    pass
            results.append(f"[skill] {entry} — {desc or '(read SKILL.md for details)'}")

    if not results:
        return ToolResult(
            True,
            output=(
                f"No tools or skills matching '{query}'.\n"
                f"Search skills.sh ecosystem: `run_command('npx skills find {query}')`"
            ),
        )

    return ToolResult(True, output=f"Tools matching '{query}':\n\n" + "\n".join(results))


TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "search_tools",
        "description": (
            "Find available tools and installed skills by keyword. "
            "Always call this before telling the user a capability doesn't exist. "
            "Examples: search_tools(query='docker'), search_tools(query='pdf'), search_tools(query='gmail')"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword to search for"},
            },
            "required": ["query"],
        },
    },
}
