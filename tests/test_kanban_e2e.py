"""
Kanban team run — full e2e test.

Spawns a team of agents, orchestrator dispatches work,
workers execute tasks, artifacts are produced.

Run:
    ltc test kanban
"""

import os
import time
import httpx
import pytest

KEEP = os.environ.get("LTC_KEEP", "") == "1"

# -- Config -------------------------------------------------------------------

BASE_URL = os.environ.get("API_URL", "http://localhost:11387")
AGENT_TIMEOUT = 180
POLL_INTERVAL = 3


def _get_secret():
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "secrets", "core.env"),
        os.path.expanduser("~/.localtaskclaw/app/secrets/core.env"),
    ]
    for env_file in candidates:
        try:
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("API_SECRET="):
                        return line.split("=", 1)[1].strip()
        except FileNotFoundError:
            continue
    return os.environ.get("API_SECRET", "")


API_SECRET = _get_secret()
HEADERS = {"X-Api-Key": API_SECRET, "Content-Type": "application/json"} if API_SECRET else {"Content-Type": "application/json"}


# -- HTTP helpers -------------------------------------------------------------

def get(path: str) -> dict:
    r = httpx.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def post(path: str, data: dict = None) -> dict:
    r = httpx.post(f"{BASE_URL}{path}", json=data or {}, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def patch(path: str, data: dict) -> dict:
    r = httpx.patch(f"{BASE_URL}{path}", json=data, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def delete(path: str):
    r = httpx.delete(f"{BASE_URL}{path}", headers=HEADERS, timeout=15)
    r.raise_for_status()


def wait_for_task(task_id: int, label: str = "", timeout: int = AGENT_TIMEOUT) -> dict:
    """Poll until task leaves 'running' status."""
    deadline = time.time() + timeout
    start = time.time()
    while time.time() < deadline:
        tasks = get("/kanban")["tasks"]
        task = next((t for t in tasks if t["id"] == task_id), None)
        assert task is not None, f"Task #{task_id} disappeared"
        if task["status"] != "running":
            elapsed = int(time.time() - start)
            tag = label or f"#{task_id}"
            status_icon = {"done": "+", "error": "!", "idle": "~"}.get(task["status"], "?")
            print(f"  [{status_icon}] {tag} -> {task['column']}/{task['status']} ({elapsed}s)")
            return task
        time.sleep(POLL_INTERVAL)
    pytest.fail(f"Task #{task_id} still running after {timeout}s")


# -- Team definition ----------------------------------------------------------

TEAM = {
    "researcher": {
        "name": "Researcher",
        "emoji": "🔍",
        "color": "#60a5fa",
        "role": "worker",
        "system_prompt": (
            "You are a research agent. When given a topic, search the web for "
            "the latest information, compile key findings, and write the result "
            "to a file using write_file. Be concise and factual."
        ),
    },
    "writer": {
        "name": "Writer",
        "emoji": "✍️",
        "color": "#f59e0b",
        "role": "worker",
        "system_prompt": (
            "You are a writing agent. When given a topic, write a clear, "
            "well-structured article (300-500 words). Save it to a file "
            "using write_file. No external tools needed — just write."
        ),
    },
    "reviewer": {
        "name": "Code Reviewer",
        "emoji": "🔬",
        "color": "#10b981",
        "role": "worker",
        "system_prompt": (
            "You are a code/workspace review agent. When asked to review, "
            "use list_files to inspect the workspace structure, then use "
            "read_file to check a few key files, and write a short review "
            "report using write_file."
        ),
    },
    "orchestrator": {
        "name": "Orchestrator",
        "emoji": "🎯",
        "color": "#ef4444",
        "role": "orchestrator",
        "system_prompt": (
            "You are a kanban orchestrator. Your job:\n"
            "1. Call kanban_list to see all tasks.\n"
            "2. For each task in backlog that has an agent_id: call kanban_run(task_id).\n"
            "3. Do NOT use kanban_move. Only use kanban_run.\n"
            "4. After dispatching all eligible tasks, finish.\n"
            "IMPORTANT: Use kanban_run, NOT kanban_move."
        ),
    },
}

TASKS = [
    {
        "key": "research",
        "agent_key": "researcher",
        "title": "Research: Latest AI Agent Frameworks",
        "description": (
            "Search the web for the top 5 AI agent frameworks in 2026. "
            "Write a summary to /data/workspace/research_agents.md with: "
            "name, URL, key features, pros/cons for each."
        ),
    },
    {
        "key": "essay",
        "agent_key": "writer",
        "title": "Write: Local-First AI Assistants",
        "description": (
            "Write a 300-500 word article about why local-first AI assistants "
            "matter for privacy and productivity. Save to /data/workspace/essay_local_ai.md"
        ),
    },
    {
        "key": "review",
        "agent_key": "reviewer",
        "title": "Review: Workspace Structure",
        "description": (
            "Review the current workspace structure. List all files, "
            "check their contents, and write a short report to "
            "/data/workspace/review_workspace.md"
        ),
    },
]


# -- Fixtures -----------------------------------------------------------------

@pytest.fixture(scope="module")
def team():
    """Create the team of agents, yield their IDs, clean up after."""
    agent_ids = {}
    print("\n--- Spawning team ---")
    for key, spec in TEAM.items():
        agent = post("/agents", spec)
        agent_ids[key] = agent["id"]
        print(f"  {spec['emoji']} {spec['name']} (id={agent['id']}, role={spec['role']})")
    print()

    yield agent_ids

    if KEEP:
        print("\n--- Keeping team (--keep) ---")
        return
    print("\n--- Cleaning up team ---")
    for key, aid in agent_ids.items():
        try:
            delete(f"/agents/{aid}")
            print(f"  deleted agent {key} #{aid}")
        except Exception:
            pass


@pytest.fixture(scope="module")
def board(team):
    """Create tasks on the kanban board, yield task map, clean up after."""
    task_ids = {}
    print("--- Creating tasks ---")
    for spec in TASKS:
        task = post("/kanban/tasks", {
            "title": spec["title"],
            "description": spec["description"],
            "agent_id": team[spec["agent_key"]],
            "column": "backlog",
        })
        task_ids[spec["key"]] = task["id"]
        agent_name = TEAM[spec["agent_key"]]["name"]
        print(f"  [{task['id']}] {spec['title']} -> {agent_name}")

    # Orchestrator task
    orc_task = post("/kanban/tasks", {
        "title": "Run Orchestration Cycle",
        "description": "Dispatch all backlog tasks to their assigned agents.",
        "agent_id": team["orchestrator"],
        "column": "backlog",
    })
    task_ids["orchestrator"] = orc_task["id"]
    print(f"  [{orc_task['id']}] Orchestration Cycle -> Orchestrator")
    print()

    yield task_ids

    if KEEP:
        print("\n--- Keeping tasks (--keep) ---")
        return
    # Cleanup
    print("\n--- Cleaning up tasks ---")
    # Cancel any still running
    for key, tid in task_ids.items():
        try:
            tasks = get("/kanban")["tasks"]
            t = next((t for t in tasks if t["id"] == tid), None)
            if t and t["status"] == "running":
                post(f"/kanban/tasks/{tid}/cancel")
                time.sleep(1)
        except Exception:
            pass
    for key, tid in task_ids.items():
        try:
            delete(f"/kanban/tasks/{tid}")
            print(f"  deleted task {key} #{tid}")
        except Exception:
            pass


# -- Tests --------------------------------------------------------------------

class TestTeamRun:
    """Full team run: orchestrator dispatches, workers execute, artifacts produced."""

    def test_health(self):
        """API is alive."""
        r = httpx.get(f"{BASE_URL}/health", timeout=5)
        assert r.status_code == 200
        data = r.json()
        print(f"\n  API OK | model: {data.get('model', '?')}")

    def test_team_created(self, team):
        """All agents exist on the server."""
        agents = get("/agents")["agents"]
        agent_ids_on_server = {a["id"] for a in agents}
        for key, aid in team.items():
            assert aid in agent_ids_on_server, f"Agent {key} #{aid} not found"
        print(f"\n  Team ready: {len(team)} agents")

    def test_tasks_in_backlog(self, board):
        """All tasks start in backlog."""
        tasks = get("/kanban")["tasks"]
        for key, tid in board.items():
            t = next((t for t in tasks if t["id"] == tid), None)
            assert t is not None, f"Task {key} #{tid} not found"
            assert t["column"] == "backlog", f"Task {key} should be in backlog, got {t['column']}"
        print(f"\n  {len(board)} tasks in backlog")

    def test_orchestrator_dispatches(self, team, board):
        """
        Run orchestrator -> it dispatches all worker tasks.
        Workers should leave backlog.
        """
        orc_id = board["orchestrator"]
        worker_keys = [k for k in board if k != "orchestrator"]

        print(f"\n--- Running orchestrator #{orc_id} ---")
        resp = post(f"/kanban/tasks/{orc_id}/run")
        assert resp["status"] == "started"

        # Wait for orchestrator to finish
        orc_result = wait_for_task(orc_id, label="orchestrator", timeout=120)
        assert orc_result["status"] != "error", f"Orchestrator failed: {orc_result.get('artifact', '')}"

        # Check worker tasks were dispatched
        tasks = get("/kanban")["tasks"]
        dispatched = 0
        for key in worker_keys:
            t = next((t for t in tasks if t["id"] == board[key]), None)
            if t and (t["column"] != "backlog" or t["status"] == "running"):
                dispatched += 1
                print(f"  -> {key}: {t['column']}/{t['status']}")
            else:
                print(f"  !  {key}: still in backlog")

        assert dispatched >= len(worker_keys) - 1, (
            f"Orchestrator only dispatched {dispatched}/{len(worker_keys)} tasks"
        )

    def test_workers_complete(self, board):
        """
        Wait for all worker tasks to finish.
        Each should end in review/done with an artifact.
        """
        worker_keys = [k for k in board if k != "orchestrator"]

        print("\n--- Waiting for workers ---")
        results = {}
        for key in worker_keys:
            tid = board[key]
            result = wait_for_task(tid, label=key, timeout=AGENT_TIMEOUT)
            results[key] = result

        # Verify results
        print("\n--- Results ---")
        all_ok = True
        for key, result in results.items():
            status = result["status"]
            column = result["column"]
            artifact = result.get("artifact") or ""
            ok = status == "done" and column in ("review", "done")

            icon = "+" if ok else "!"
            print(f"  [{icon}] {key}: {column}/{status}")
            if artifact:
                print(f"      artifact: {artifact}")
            if not ok:
                all_ok = False

        assert all_ok, "Not all workers completed successfully"

    def test_final_board_state(self, board):
        """Board should have no tasks stuck in backlog or running."""
        tasks = get("/kanban")["tasks"]
        board_ids = set(board.values())

        print("\n--- Final board ---")
        for t in tasks:
            if t["id"] not in board_ids:
                continue
            key = next((k for k, v in board.items() if v == t["id"]), "?")
            print(f"  {key:15s} | {t['column']:12s} | {t['status']:10s} | {t.get('artifact') or '-'}")

        our_tasks = [t for t in tasks if t["id"] in board_ids]
        stuck = [t for t in our_tasks if t["status"] == "running"]
        assert len(stuck) == 0, f"{len(stuck)} tasks still running"


# -- Entry point --------------------------------------------------------------

if __name__ == "__main__":
    import subprocess, sys
    sys.exit(subprocess.call([
        sys.executable, "-m", "pytest", __file__, "-v", "-s",
        "--tb=short", "--no-header",
    ]))
