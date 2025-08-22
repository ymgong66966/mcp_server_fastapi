import asyncio
import os
from fastmcp import FastMCP
from online_search_mcp import online_mcp
from starlette.requests import Request
from starlette.responses import PlainTextResponse

# Get configuration from environment variables at module level
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

print(f"Configuring MCP server for {HOST}:{PORT}")

# Create the main MCP server
mcp = FastMCP("main-mcp")

@mcp.tool
def add(a: int, b: int) -> int:
    """Adds two integer numbers together."""
    return a + b

@mcp.tool(
    name="find_products",
    description="Search the product catalog with optional category filtering.",
    tags={"catalog", "search"},
)
def search_products_implementation(query: str, category: str | None = None) -> list[dict]:
    """Internal function description (ignored if description is provided above)."""
    print(f"Searching for '{query}' in category '{category}'")
    return [{"id": 2, "name": "Another Product"}]

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    """Health check endpoint for Kubernetes"""
    return PlainTextResponse("OK")

@mcp.custom_route("/ready", methods=["GET"])
async def readiness_check(request: Request) -> PlainTextResponse:
    """Readiness check endpoint for Kubernetes"""
    return PlainTextResponse("READY")

# Mount the subserver (updated syntax to fix deprecation warning)
mcp.mount(online_mcp, "/online")

print(f"Mounted subservers: /online")

# Keep the main function for running the FastMCP server
async def main():
    print(f"Starting MCP server on {HOST}:{PORT}")
    
    # Run the server with HTTP transport
    await mcp.run_async(
        transport="http",
        host=HOST,
        port=PORT
    )

# Run the server when the module is imported (for container deployment)
if __name__ == "__main__":
    # This runs when called directly (python main.py)
    asyncio.run(main())
else:
    # This runs when imported by container - start the server immediately
    import asyncio
    asyncio.run(main())