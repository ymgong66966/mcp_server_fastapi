import asyncio
import json
import os
from typing import List
from fastmcp import FastMCP
from mcp import ClientSession, StdioServerParameters, stdio_client
from web_map_zilliz_trie import zilliz_url_trie
from google_maps_api import GooglePlacesAPI
online_mcp = FastMCP(name="online-search-mcp")

@online_mcp.tool(
        name="general_online_search_with_one_query",           # Custom tool name for the LLM
    description="""get information from the internet about something asked by user. Best for: Finding specific information across multiple websites, when you don't know which website has the information.
When you need the most relevant content for a query

Not recommended for: When you already know which website to scrape (use scrape)
When you need comprehensive coverage of a single website (use map or crawl)
""", # Custom description
    tags={ "online search"},      # Optional tags for organization/filtering
    
)
async def online_search_implementation(query: str) -> list[dict]:
    """Internal function description (ignored if description is provided above)."""
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "firecrawl-mcp"],
        env={"FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY", "fc-4e2dd3f9580f4c9094fd3ef5d2a02d97")},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1) List available tools
            tools_resp = await session.list_tools()
            print("Tools:", [t.name for t in tools_resp.tools])

            # 2) Find firecrawl_search and show its input schema
            search_tool = next((t for t in tools_resp.tools if t.name == "firecrawl_search"), None)
            if not search_tool:
                raise RuntimeError("firecrawl_search tool not found. Check tool names printed above.")
            print("\nfirecrawl_search input schema:")
            print(json.dumps(search_tool.inputSchema or {}, indent=2))

            # Use the actual query parameter instead of hardcoded value
            args = {
                "query": query,
                "limit": 3,
                "sources": [{"type": "web"}]
            }

            result = await session.call_tool("firecrawl_search", args)
            print(result)
            
            # Return the actual search results
            if hasattr(result, 'content') and result.content:
                return result.content
            else:
                return [{"result": f"couldn't retrieve results for: {query}"}]

@online_mcp.tool(
        name="scrape_multiple_websites_after_website_map",           # Custom tool name for the LLM
    description="""get information from the internet about something asked by user. Best for: Finding specific information across multiple websites, when you don't know which website has the information.
When you need the most relevant content for a query

Not recommended for: When you already know which website to scrape (use scrape)
When you need comprehensive coverage of a single website (use map or crawl)
""", # Custom description
    tags={ "online search"},      # Optional tags for organization/filtering
    
)
async def scrape_multiple_websites_implementation(urls: list[str], queries: list[str]) -> list[dict]:
    """Scrape multiple websites concurrently with proper error handling."""
    
    # Input validation
    if not urls:
        return [{"error": "No URLs provided"}]
    if not queries:
        return [{"error": "No queries provided"}]
    
    # Limit concurrent requests to avoid overwhelming servers
    MAX_CONCURRENT = 5
    if len(urls) > MAX_CONCURRENT:
        urls = urls[:MAX_CONCURRENT]
    
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "firecrawl-mcp"],
        env={"FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY", "fc-4e2dd3f9580f4c9094fd3ef5d2a02d97")},
    )
    
    extract_prompt = (
        f"queries: {str(queries)}\n"
        "answer: answer with the information you get from the website. "
        "if cannot find answer, return 'answer not found'"
    )

    schema = {
        "type": "object",
        "properties": {
            "queries": {"type": "string"},
            "answer": {"type": "string"},
        },
        "required": ["queries", "answer"]
    }

    async def scrape_single_url(session: ClientSession, url: str) -> dict:
        """Scrape a single URL with error handling."""
        try:
            args = {
                "url": url,
                "formats": [
                    {
                        "type": "json",
                        "prompt": extract_prompt,
                        "schema": schema
                    }
                ],
                "onlyMainContent": False,
                "removeBase64Images": True,
                "waitFor": 1500
            }
            
            result = await session.call_tool("firecrawl_scrape", args)
            
            if hasattr(result, 'content') and result.content:
                content = result.content.text if hasattr(result.content, 'text') else str(result.content)
                return {
                    "url": url,
                    "status": "success",
                    "content": content
                }
            else:
                return {
                    "url": url,
                    "status": "error",
                    "error": "No content returned"
                }
                
        except Exception as e:
            return {
                "url": url,
                "status": "error",
                "error": str(e)
            }

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Verify scrape tool is available
            try:
                tools = await session.list_tools()
                if not any(t.name == "firecrawl_scrape" for t in tools.tools):
                    return [{"error": f"firecrawl_scrape tool not found. Available tools: {[t.name for t in tools.tools]}"}]
            except Exception as e:
                return [{"error": f"Failed to list tools: {str(e)}"}]
            
            # Process URLs concurrently
            try:
                tasks = [scrape_single_url(session, url) for url in urls]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Handle any exceptions from gather
                processed_results = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        processed_results.append({
                            "url": urls[i],
                            "status": "error",
                            "error": f"Task failed: {str(result)}"
                        })
                    else:
                        processed_results.append(result)
                
                return processed_results
                
            except Exception as e:
                return [{"error": f"Failed to process URLs: {str(e)}"}]

@online_mcp.tool(name="website_map",           # Custom tool name for the LLM
    description="""get information from the internet about something asked by user. Best for: Finding specific information across multiple websites, when you don't know which website has the information.
When you need the most relevant content for a query

Not recommended for: When you already know which website to scrape (use scrape)
When you need comprehensive coverage of a single website (use map or crawl)
""", # Custom description
    tags={ "online search"})
async def website_map(domain: str, query: List[str]):
    """The purpose of this function is to retrieve relevant information from a website based on a user's query. The function takes a web domain and a list of queries as input and returns a list of relevant URLs."""
    print(domain, query, "domain and query")
    relevant_urls = await zilliz_url_trie(domain, query)
    return relevant_urls
@online_mcp.tool(name="google_places_search")
async def google_places_search(location: str, location_query: str = "") -> list[dict]:
    api = GooglePlacesAPI(api_key=os.getenv("GOOGLE_PLACES_API_KEY", "AIzaSyBkUXBC57tZH4xbPiLqqcuszmUH0VOfe8U"))
    results = await api.search_restaurants_by_text(location, location_query)
    return results
    