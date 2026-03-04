"""edit_file — targeted string replacement in files (no full rewrite needed)."""

import os
from config import CONFIG
from models import ToolResult, ToolContext


def _safe_path(cwd: str, path: str) -> str | None:
    if os.path.isabs(path):
        resolved = os.path.realpath(path)
    else:
        resolved = os.path.realpath(os.path.join(cwd, path))
    workspace = os.path.realpath(CONFIG.workspace)
    if not resolved.startswith(workspace):
        return None
    return resolved


async def tool_edit_file(args: dict, ctx: ToolContext) -> ToolResult:
    """Replace old_text with new_text in a file. Much faster than full rewrite for small changes."""
    path = args.get("path", "")
    old_text = args.get("old_text", "")
    new_text = args.get("new_text", "")
    replace_all = args.get("replace_all", False)

    if not path or old_text is None or new_text is None:
        return ToolResult(False, error="path, old_text, and new_text are required")

    safe = _safe_path(ctx.cwd, path)
    if not safe:
        return ToolResult(False, error="🚫 Path outside workspace")
    if not os.path.exists(safe):
        return ToolResult(False, error=f"File not found: {path}")

    try:
        content = open(safe, "r", errors="replace").read()

        if old_text not in content:
            return ToolResult(
                False,
                error=f"old_text not found in {path}. Use read_file first to verify exact content.",
            )

        count = content.count(old_text)
        if count > 1 and not replace_all:
            return ToolResult(
                False,
                error=f"old_text appears {count} times in file. Set replace_all=true to replace all, or use more specific text.",
            )

        new_content = content.replace(old_text, new_text) if replace_all else content.replace(old_text, new_text, 1)
        with open(safe, "w") as f:
            f.write(new_content)

        replacements = content.count(old_text) if replace_all else 1
        return ToolResult(True, output=f"Replaced {replacements} occurrence(s) in {path}")
    except Exception as e:
        return ToolResult(False, error=str(e))


TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": (
            "Replace a specific string in a file. Faster than read_file + write_file for small edits. "
            "Always read_file first to see exact content. The old_text must match exactly (whitespace included)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
                "old_text": {"type": "string", "description": "Exact text to replace"},
                "new_text": {"type": "string", "description": "Replacement text"},
                "replace_all": {
                    "type": "boolean",
                    "description": "Replace all occurrences (default false — only first)",
                },
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
}
