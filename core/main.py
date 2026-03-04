"""LocalClaw Core — entry point."""

import asyncio
import uvicorn
from config import CONFIG
from logger import core_logger
from db import init_db


async def _startup():
    init_db()
    # Initialize MCP servers if configured
    try:
        from tools.mcp import init_mcp
        await init_mcp(CONFIG.workspace)
    except Exception as e:
        core_logger.warning(f"MCP init skipped: {e}")


def main():
    core_logger.info("=" * 50)
    core_logger.info("LocalClaw Core Agent")
    core_logger.info(f"  Model:     {CONFIG.model}")
    core_logger.info(f"  LLM URL:   {CONFIG.llm_base_url}")
    core_logger.info(f"  Workspace: {CONFIG.workspace}")
    core_logger.info(f"  Port:      {CONFIG.api_port}")
    core_logger.info("=" * 50)

    asyncio.run(_startup())

    from api import app
    uvicorn.run(app, host="0.0.0.0", port=CONFIG.api_port, log_level="warning")


if __name__ == "__main__":
    main()
