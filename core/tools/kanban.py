"""Kanban tools — let agents inspect and manage the kanban board."""

import asyncio
from models import ToolResult, ToolContext
from db import (
    get_kanban_tasks, update_kanban_task, get_agents,
    create_kanban_task,
)

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "kanban_list",
            "description": (
                "List all kanban tasks grouped by column. "
                "Use this to see what tasks exist and their current status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "column": {
                        "type": "string",
                        "description": "Filter by column: backlog, in_progress, review, done. Omit for all tasks.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kanban_move",
            "description": (
                "Move a kanban task to a different column. "
                "Columns: backlog, in_progress, review, done. "
                "Moving to in_progress does NOT auto-run the agent — use kanban_run for that."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "Task ID to move"},
                    "column": {
                        "type": "string",
                        "description": "Target column: backlog, in_progress, review, done",
                    },
                },
                "required": ["task_id", "column"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kanban_run",
            "description": (
                "Run the assigned agent on a kanban task. "
                "The task must have an agent assigned. "
                "This starts the agent asynchronously — the task status will change to 'running'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "Task ID to run"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kanban_update",
            "description": "Update a kanban task's title, description, or assigned agent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "Task ID to update"},
                    "title": {"type": "string", "description": "New title (optional)"},
                    "description": {"type": "string", "description": "New description/prompt (optional)"},
                    "agent_id": {"type": "integer", "description": "Assign agent by ID (optional)"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kanban_create",
            "description": "Create a new kanban task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task title"},
                    "description": {"type": "string", "description": "Task description / agent prompt"},
                    "agent_id": {"type": "integer", "description": "Assign agent by ID (optional)"},
                    "column": {
                        "type": "string",
                        "description": "Initial column: backlog (default), in_progress, review, done",
                    },
                },
                "required": ["title"],
            },
        },
    },
]


def _fmt_tasks(tasks: list, column_filter: str | None = None) -> str:
    if column_filter:
        tasks = [t for t in tasks if t["column"] == column_filter]
    if not tasks:
        return "No tasks found."

    cols: dict[str, list] = {}
    for t in tasks:
        cols.setdefault(t["column"], []).append(t)

    lines = []
    for col, items in cols.items():
        lines.append(f"\n[{col.upper()}]")
        for t in items:
            agent = f" → {t['agent_emoji']} {t['agent_name']}" if t.get("agent_name") else " → (no agent)"
            status = f" [{t['status']}]" if t["status"] != "idle" else ""
            lines.append(f"  #{t['id']} {t['title']}{agent}{status}")
            if t.get("description"):
                lines.append(f"      {t['description'][:120]}")
    return "\n".join(lines)


async def tool_kanban_list(args: dict, ctx: ToolContext) -> ToolResult:
    column = args.get("column")
    tasks = get_kanban_tasks()
    agents = get_agents()

    summary = _fmt_tasks(tasks, column)

    # Also list available agents
    if agents:
        agent_lines = "\n\nAVAILABLE AGENTS:"
        for a in agents:
            role = a.get("role", "worker")
            agent_lines += f"\n  #{a['id']} {a['emoji']} {a['name']} [{role}]"
        summary += agent_lines

    return ToolResult(True, output=summary)


async def tool_kanban_move(args: dict, ctx: ToolContext) -> ToolResult:
    task_id = args.get("task_id")
    column = args.get("column", "").strip()

    valid_cols = {"backlog", "in_progress", "review", "done"}
    if column not in valid_cols:
        return ToolResult(False, error=f"Invalid column '{column}'. Valid: {', '.join(valid_cols)}")

    task = update_kanban_task(task_id, column=column)
    if not task:
        return ToolResult(False, error=f"Task #{task_id} not found")

    return ToolResult(True, output=f"Task #{task_id} '{task['title']}' moved to {column}")


async def tool_kanban_run(args: dict, ctx: ToolContext) -> ToolResult:
    """Trigger agent run on a task via the internal API (non-blocking)."""
    task_id = args.get("task_id")
    tasks = get_kanban_tasks()
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        return ToolResult(False, error=f"Task #{task_id} not found")
    if not task.get("agent_id"):
        return ToolResult(False, error=f"Task #{task_id} has no agent assigned")
    if task["status"] == "running":
        return ToolResult(False, error=f"Task #{task_id} is already running")

    # Import here to avoid circular imports; run_kanban_task_logic is defined in api.py
    # Use direct DB + agent call instead
    from config import CONFIG
    import httpx
    try:
        url = f"http://localhost:{CONFIG.api_port}/kanban/tasks/{task_id}/run"
        headers = {}
        if CONFIG.api_secret:
            headers["X-Api-Key"] = CONFIG.api_secret
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, headers=headers)
            if resp.status_code == 200:
                return ToolResult(True, output=f"Agent started on task #{task_id} '{task['title']}'")
            return ToolResult(False, error=f"Failed to start agent: {resp.text[:200]}")
    except Exception as e:
        return ToolResult(False, error=f"Request failed: {e}")


async def tool_kanban_update(args: dict, ctx: ToolContext) -> ToolResult:
    task_id = args.get("task_id")
    fields = {k: v for k, v in args.items() if k != "task_id" and v is not None}
    if not fields:
        return ToolResult(False, error="No fields to update")
    task = update_kanban_task(task_id, **fields)
    if not task:
        return ToolResult(False, error=f"Task #{task_id} not found")
    return ToolResult(True, output=f"Task #{task_id} updated: {task['title']}")


async def tool_kanban_create(args: dict, ctx: ToolContext) -> ToolResult:
    title = args.get("title", "").strip()
    if not title:
        return ToolResult(False, error="title is required")
    description = args.get("description", "")
    agent_id = args.get("agent_id")
    column = args.get("column", "backlog")

    valid_cols = {"backlog", "in_progress", "review", "done"}
    if column not in valid_cols:
        column = "backlog"

    task = create_kanban_task(title, description, agent_id, column)
    return ToolResult(True, output=f"Task #{task['id']} created: '{title}' in {column}")
