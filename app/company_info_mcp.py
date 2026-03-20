"""
WithCare Company Info MCP — serves authoritative company knowledge.

Reads company_knowledge.md at startup and returns it when called.
The calling LLM extracts the relevant section based on the user's query.
"""

import os
from pathlib import Path

from fastmcp import FastMCP

company_info_mcp = FastMCP(name="company-info-mcp")

# Load knowledge base once at startup
_KB_PATH = Path(__file__).parent / "company_knowledge.md"
_KNOWLEDGE_CONTENT = ""

try:
    _KNOWLEDGE_CONTENT = _KB_PATH.read_text(encoding="utf-8")
except Exception as e:
    print(f"[company_info_mcp] WARNING: Could not load {_KB_PATH}: {e}")


@company_info_mcp.tool(
    name="get_withcare_info",
    description=(
        "Returns authoritative information about the WithCare platform/app/company. "
        "Covers: product features, account management, care circles, the Navigator, "
        "privacy/HIPAA/data security, pricing, device support, company mission, "
        "contacting support, and FAQ. Use ONLY when the user asks about WithCare "
        "itself — NOT for general caregiving, medical, or insurance questions."
    ),
    tags={"company", "withcare", "faq"},
)
async def get_withcare_info(query: str) -> dict:
    """Return WithCare company knowledge for a user query."""
    if not _KNOWLEDGE_CONTENT:
        return {
            "content": "WithCare company information is not yet configured. "
                       "Please contact support for details.",
            "source": "company_kb",
            "status": "empty",
        }

    return {
        "content": _KNOWLEDGE_CONTENT,
        "source": "company_kb",
        "query": query,
        "status": "ok",
    }
