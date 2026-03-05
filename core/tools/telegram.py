"""Telegram notify tool — lets agents send messages to the owner chat."""

import httpx
from models import ToolResult, ToolContext
from config import CONFIG
from logger import core_logger

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "telegram_notify",
        "description": (
            "Send a Telegram message to the owner. "
            "Use this when you need to report results, ask a question, or notify about task completion."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Message text to send (Markdown supported)",
                },
            },
            "required": ["text"],
        },
    },
}


async def tool_telegram_notify(args: dict, ctx: ToolContext) -> ToolResult:
    text = args.get("text", "").strip()
    if not text:
        return ToolResult(False, error="text is required")

    bot_token = CONFIG.bot_token
    owner_id = CONFIG.owner_id

    if not bot_token:
        return ToolResult(False, error="BOT_TOKEN not configured")
    if not owner_id:
        return ToolResult(False, error="OWNER_ID not configured")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": owner_id,
        "text": text,
        "parse_mode": "Markdown",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                core_logger.info(f"Telegram notify sent to {owner_id}")
                return ToolResult(True, output=f"Message sent to Telegram owner ({owner_id})")
            else:
                # Retry without Markdown if parse failed
                if resp.status_code == 400 and "parse" in resp.text.lower():
                    payload2 = {"chat_id": owner_id, "text": text}
                    resp2 = await client.post(url, json=payload2)
                    if resp2.status_code == 200:
                        return ToolResult(True, output=f"Message sent (plain text) to Telegram owner ({owner_id})")
                    return ToolResult(False, error=f"Telegram API error {resp2.status_code}: {resp2.text[:200]}")
                return ToolResult(False, error=f"Telegram API error {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        core_logger.error(f"telegram_notify error: {e}")
        return ToolResult(False, error=f"Request failed: {e}")
