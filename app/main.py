import asyncio
import os
from pathlib import Path
from fastmcp import FastMCP
from fastmcp.server.providers import FileSystemProvider
from online_search_mcp import online_mcp
from follow_up_mcp import follow_up_mcp
from starlette.requests import Request
from starlette.responses import PlainTextResponse

# Get configuration from environment variables at module level
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

print(f"Configuring MCP server for {HOST}:{PORT}")

# Create the main MCP server with FileSystemProvider for auto-discovered tools
mcp = FastMCP(
    "main-mcp",
    providers=[
        FileSystemProvider(Path(__file__).parent / "tools"),
    ],
)

# Health and readiness endpoints
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    """Health check endpoint for Kubernetes"""
    return PlainTextResponse("OK")

@mcp.custom_route("/ready", methods=["GET"])
async def readiness_check(request: Request) -> PlainTextResponse:
    """Readiness check endpoint for Kubernetes"""
    return PlainTextResponse("READY")

# Mount sub-servers WITHOUT namespace to preserve exact tool names
mcp.mount(online_mcp)
mcp.mount(follow_up_mcp)
print("Mounted sub-servers: online_mcp, follow_up_mcp")

# --- Optional: Namespace transform example (commented out) ---
# To namespace-prefix tools from a sub-server (e.g., "online_" prefix):
#
#   from fastmcp.server.transforms import Namespace
#   namespaced_online = Namespace(online_mcp, prefix="online")
#   mcp.mount(namespaced_online)
#
# This would rename tools like "website_map" → "online_website_map".
# NOT used here to keep tool names identical for existing LLM consumers.
# ---


# Keep the main function for running the FastMCP server
async def main():
    print(f"Starting MCP server on {HOST}:{PORT}")

    # Run the server with HTTP transport
    await mcp.run_async(
        transport="http",
        host=HOST,
        port=PORT,
    )


# Run the server when the module is imported (for container deployment)
if __name__ == "__main__":
    # This runs when called directly (python main.py)
    asyncio.run(main())
else:
    # This runs when imported by container - start the server immediately
    import asyncio
    asyncio.run(main())
