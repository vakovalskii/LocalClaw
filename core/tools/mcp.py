"""MCP (Model Context Protocol) — subprocess stdio transport.

Config file: {workspace}/mcp_servers.json or /data/mcp_servers.json
Format:
{
  "servers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {"GITHUB_TOKEN": "..."}
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/data/workspace"]
    }
  }
}

Tools are exposed as mcp_{server_name}_{tool_name}.
"""

import asyncio
import json
import os
from dataclasses import dataclass, field
from logger import tool_logger
from models import ToolResult, ToolContext


@dataclass
class McpServer:
    name: str
    command: str
    args: list
    env: dict = field(default_factory=dict)
    process: asyncio.subprocess.Process | None = None
    tools: list = field(default_factory=list)
    _req_id: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def start(self):
        env = {**os.environ, **self.env}
        self.process = await asyncio.create_subprocess_exec(
            self.command, *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        # Initialize MCP handshake
        await self._send({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "LocalTaskClaw", "version": "0.1.0"},
            },
        })
        await self._recv()
        await self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        # Discover tools
        await self._load_tools()
        tool_logger.info(f"MCP server '{self.name}' started, {len(self.tools)} tools")

    async def _load_tools(self):
        resp = await self._call("tools/list", {})
        self.tools = resp.get("tools", [])

    async def call_tool(self, tool_name: str, args: dict) -> dict:
        return await self._call("tools/call", {"name": tool_name, "arguments": args})

    async def _call(self, method: str, params: dict) -> dict:
        req_id = self._next_id()
        await self._send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})
        resp = await self._recv()
        if "error" in resp:
            raise RuntimeError(f"MCP error: {resp['error']}")
        return resp.get("result", {})

    async def _send(self, msg: dict):
        line = json.dumps(msg) + "\n"
        self.process.stdin.write(line.encode())
        await self.process.stdin.drain()

    async def _recv(self) -> dict:
        try:
            line = await asyncio.wait_for(self.process.stdout.readline(), timeout=30)
            return json.loads(line.decode())
        except asyncio.TimeoutError:
            raise RuntimeError("MCP server response timeout")

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass


class McpManager:
    """Manages a set of MCP server subprocesses."""

    def __init__(self):
        self._servers: dict[str, McpServer] = {}
        self._started = False

    def load_config(self, config_paths: list[str]):
        """Load server configs from JSON files."""
        for path in config_paths:
            if not os.path.exists(path):
                continue
            try:
                data = json.loads(open(path).read())
                for name, cfg in data.get("servers", {}).items():
                    self._servers[name] = McpServer(
                        name=name,
                        command=cfg["command"],
                        args=cfg.get("args", []),
                        env=cfg.get("env", {}),
                    )
                tool_logger.info(f"MCP config loaded from {path}: {list(self._servers.keys())}")
            except Exception as e:
                tool_logger.warning(f"MCP config load failed {path}: {e}")

    async def start_all(self):
        if self._started:
            return
        self._started = True
        for name, server in list(self._servers.items()):
            try:
                await server.start()
            except Exception as e:
                tool_logger.warning(f"MCP server '{name}' failed to start: {e}")
                del self._servers[name]

    def get_all_tools(self) -> list[dict]:
        """Return tool definitions for all MCP servers (as mcp_{server}_{tool})."""
        defs = []
        for server_name, server in self._servers.items():
            for tool in server.tools:
                defs.append({
                    "type": "function",
                    "source": f"mcp:{server_name}",
                    "function": {
                        "name": f"mcp_{server_name}_{tool['name']}",
                        "description": tool.get("description", ""),
                        "parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
                    },
                })
        return defs

    async def call(self, full_tool_name: str, args: dict) -> ToolResult:
        """Dispatch mcp_{server}_{tool} call."""
        if not full_tool_name.startswith("mcp_"):
            return ToolResult(False, error=f"Not an MCP tool: {full_tool_name}")

        # Parse server name from tool name — try all known servers
        rest = full_tool_name[4:]
        server = None
        tool_name = None
        for sname in sorted(self._servers.keys(), key=len, reverse=True):
            prefix = sname + "_"
            if rest.startswith(prefix):
                server = self._servers[sname]
                tool_name = rest[len(prefix):]
                break

        if not server or not tool_name:
            return ToolResult(False, error=f"Unknown MCP tool: {full_tool_name}")

        try:
            result = await server.call_tool(tool_name, args)
            # Extract text content from MCP response
            content = result.get("content", [])
            if isinstance(content, list):
                texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                output = "\n".join(texts) if texts else json.dumps(result)
            else:
                output = str(result)
            return ToolResult(True, output=output)
        except Exception as e:
            return ToolResult(False, error=str(e))

    def stop_all(self):
        for server in self._servers.values():
            server.stop()


# Singleton
mcp_manager = McpManager()


async def init_mcp(workspace: str):
    """Load MCP config and start servers. Call once at startup."""
    config_paths = [
        "/data/mcp_servers.json",
        os.path.join(workspace, "mcp_servers.json"),
    ]
    mcp_manager.load_config(config_paths)
    if mcp_manager._servers:
        await mcp_manager.start_all()
    else:
        tool_logger.info("No MCP servers configured (create mcp_servers.json to add)")
