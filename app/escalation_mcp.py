import os
import logging

import httpx
from fastmcp import FastMCP

_logger = logging.getLogger(__name__)

escalation_mcp = FastMCP(name="escalation-mcp")

DELIVER_NAVIGATOR_URL = os.getenv("DELIVER_NAVIGATOR_URL", "")
LAMBDA_API_KEY = os.getenv("LAMBDA_API_KEY", "")


@escalation_mcp.tool(
    name="human_escalation_deliver",
    description=(
        "Deliver user messages to the human support team via the "
        "DeliverNavigatorMessage lambda. Called when the agent determines "
        "that a human clinical team should take over the conversation."
    ),
    tags={"escalation", "human-support"},
)
async def human_escalation_deliver(
    user_id: str,
    chat_id: str,
    messages: list[dict],
) -> dict:
    """Deliver messages to human support team.

    Args:
        user_id: The user identifier.
        chat_id: The conversation/chat identifier.
        messages: List of message dicts with keys: role, text, message_Id, dateSent.

    Returns:
        dict with status and response, or error details.
    """
    if not DELIVER_NAVIGATOR_URL:
        return {"error": "DELIVER_NAVIGATOR_URL not configured"}

    payload = {
        "user_Id": user_id,
        "chat_Id": chat_id,
        "messages": messages,
        "needs_human": True,
    }

    headers = {"Content-Type": "application/json"}
    if LAMBDA_API_KEY:
        headers["x-api-key"] = LAMBDA_API_KEY

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                DELIVER_NAVIGATOR_URL,
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            return {"status": "delivered", "response": resp.json()}
    except httpx.HTTPStatusError as e:
        _logger.error(f"Escalation delivery HTTP error: {e.response.status_code} {e.response.text}")
        return {"error": f"HTTP {e.response.status_code}", "detail": e.response.text}
    except Exception as e:
        _logger.error(f"Escalation delivery failed: {e}")
        return {"error": str(e)}
