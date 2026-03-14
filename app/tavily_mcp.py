"""
Tavily Search MCP — LLM-optimized web search and content extraction.

Provides two tools:
  1. tavily_search       — basic search (fast, 1 credit, snippets + AI answer)
  2. tavily_search_deep  — advanced search (deeper, raw content + AI answer)
"""

import os
from typing import Optional

import httpx
from fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

tavily_mcp = FastMCP(name="tavily-search-mcp")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_API_BASE = "https://api.tavily.com"


async def _tavily_request(endpoint: str, payload: dict, timeout: float = 30.0) -> dict:
    """Make a request to the Tavily API."""
    payload["api_key"] = TAVILY_API_KEY
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{TAVILY_API_BASE}/{endpoint}", json=payload)
        resp.raise_for_status()
        return resp.json()


def _format_results(data: dict, include_raw: bool = False) -> list[dict]:
    """Format Tavily response into a clean result list."""
    output = []

    answer = data.get("answer")
    if answer:
        output.append({
            "type": "ai_answer",
            "content": answer,
        })

    for r in data.get("results", []):
        item = {
            "url": r.get("url", ""),
            "title": r.get("title", ""),
            "content": r.get("content", ""),
            "score": r.get("score", 0),
        }
        if include_raw and r.get("raw_content"):
            item["raw_content"] = r["raw_content"][:5000]
        output.append(item)

    return output


@tavily_mcp.tool(
    name="tavily_search",
    description="""Search the web using Tavily's LLM-optimized search API. Returns clean, relevant
content snippets plus an AI-synthesized answer. Best for: quick factual queries, general knowledge
questions, policy lookups, definitions. Returns better content quality than traditional search APIs
because results are cleaned and optimized for AI consumption.

Input: query (string) — a descriptive, natural-language search query. Longer, more specific queries
produce better results than short keyword queries.

Example: "What are the Medicaid eligibility requirements in California for elderly adults 2026"
""",
    tags={"online search", "tavily"},
)
async def tavily_search(
    query: str,
    max_results: int = 5,
) -> list[dict]:
    """Basic Tavily search — fast, returns snippets + AI answer."""
    if not TAVILY_API_KEY:
        return [{"error": "TAVILY_API_KEY not configured"}]

    try:
        data = await _tavily_request("search", {
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": True,
            "include_raw_content": False,
        })
        return _format_results(data, include_raw=False)
    except Exception as e:
        return [{"error": f"Tavily search failed: {str(e)}"}]


@tavily_mcp.tool(
    name="tavily_search_deep",
    description="""Deep search using Tavily's advanced mode. Returns comprehensive content including
full page text plus an AI-synthesized answer. Best for: finding specific services with requirements
(language, budget, location), comparing providers, getting detailed information about care options.

This tool excels when the query includes specific constraints like geographic area, language
preferences, budget limits, or specialized care needs. Use descriptive, sentence-length queries
rather than short keywords.

Input: query (string), max_results (int, default 5), include_domains (optional list of domain strings
to restrict search to), exclude_domains (optional list of domains to exclude).

Example: "Mandarin speaking in-home caregiver services Los Angeles California under $30 per hour for elderly father with back pain"
""",
    tags={"online search", "tavily"},
)
async def tavily_search_deep(
    query: str,
    max_results: int = 5,
    include_domains: Optional[list[str]] = None,
    exclude_domains: Optional[list[str]] = None,
) -> list[dict]:
    """Advanced Tavily search — deeper, returns raw content + AI answer."""
    if not TAVILY_API_KEY:
        return [{"error": "TAVILY_API_KEY not configured"}]

    try:
        payload = {
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_answer": True,
            "include_raw_content": True,
        }
        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains

        data = await _tavily_request("search", payload, timeout=60.0)
        return _format_results(data, include_raw=True)
    except Exception as e:
        return [{"error": f"Tavily deep search failed: {str(e)}"}]
