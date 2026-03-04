"""Tool registry — maps tool names to async handlers and provides definitions."""

from models import ToolResult, ToolContext
from tools.bash import tool_run_command, TOOL_DEFINITION as BASH_DEF
from tools.web import tool_search_web, tool_fetch_page, TOOL_DEFINITIONS as WEB_DEFS
from tools.files import (
    tool_read_file, tool_write_file, tool_list_files, tool_delete_file,
    TOOL_DEFINITIONS as FILE_DEFS,
)
from tools.memory import tool_memory, TOOL_DEFINITION as MEMORY_DEF
from tools.scheduler import tool_schedule, TOOL_DEFINITION as SCHEDULER_DEF
from tools.search_tools import tool_search_tools, TOOL_DEFINITION as SEARCH_TOOLS_DEF
from tools.edit import tool_edit_file, TOOL_DEFINITION as EDIT_DEF


_BUILTIN_HANDLERS = {
    "run_command": tool_run_command,
    "search_web": tool_search_web,
    "fetch_page": tool_fetch_page,
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "list_files": tool_list_files,
    "delete_file": tool_delete_file,
    "memory": tool_memory,
    "schedule_task": tool_schedule,
    "search_tools": tool_search_tools,
    "edit_file": tool_edit_file,
}

_DEFINITIONS = [BASH_DEF] + WEB_DEFS + FILE_DEFS + [EDIT_DEF, MEMORY_DEF, SCHEDULER_DEF, SEARCH_TOOLS_DEF]


def get_tool_definitions() -> list:
    """Return all tool definitions: builtins + active MCP tools."""
    defs = list(_DEFINITIONS)
    try:
        from tools.mcp import mcp_manager
        defs.extend(mcp_manager.get_all_tools())
    except Exception:
        pass
    return defs


async def execute_tool(name: str, args: dict, ctx: ToolContext) -> ToolResult:
    # Built-in tools
    handler = _BUILTIN_HANDLERS.get(name)
    if handler:
        try:
            return await handler(args, ctx)
        except Exception as e:
            return ToolResult(False, error=f"Tool error: {e}")

    # MCP tools
    if name.startswith("mcp_"):
        try:
            from tools.mcp import mcp_manager
            return await mcp_manager.call(name, args)
        except Exception as e:
            return ToolResult(False, error=f"MCP error: {e}")

    return ToolResult(False, error=f"Unknown tool: {name}")
