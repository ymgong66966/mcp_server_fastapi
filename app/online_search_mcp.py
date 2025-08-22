import asyncio
from fastmcp import FastMCP

online_mcp = FastMCP(name="online-search-mcp")

@online_mcp.tool(
        name="online_search",           # Custom tool name for the LLM
    description="get information from the internet about something asked by user", # Custom description
    tags={ "online search"},      # Optional tags for organization/filtering
    
)
def online_search_implementation(query: str) -> list[dict]:
    """Internal function description (ignored if description is provided above)."""
    # Implementation...
    print(f"Conducting online search about'{query}'")
    return [{"result": "Yiming's mom's birthday is on 2025-08-15"}]

