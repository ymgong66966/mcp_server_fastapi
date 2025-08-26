import asyncio
import json
import os
from typing import List
from fastmcp import FastMCP
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
    """Direct Firecrawl API search implementation."""
    try:
        from firecrawl import Firecrawl
        
        # Initialize Firecrawl client with default API key
        app = Firecrawl(api_key=os.getenv("FIRECRAWL_API_KEY", "fc-4e2dd3f9580f4c9094fd3ef5d2a02d97"))
        
        # Debug: Show what we're searching for
        print(f"🔍 Searching for: {query}")
        
        # Perform search using Firecrawl's search functionality
        search_result = app.search(
            sources=["web"],
            query=query,
            limit=3
        )
        
        # Debug: Show raw result
        print(f"🔍 Raw search result: {search_result}")
        
        if search_result:
            # Try different possible data structures
            if isinstance(search_result, list):
                return search_result if search_result else [{"result": f"No results found for: {query}"}]
            elif isinstance(search_result, dict):
                if 'data' in search_result:
                    return search_result['data'] if search_result['data'] else [{"result": f"No results found for: {query}"}]
                elif 'results' in search_result:
                    return search_result['results'] if search_result['results'] else [{"result": f"No results found for: {query}"}]
                else:
                    return [search_result]
            else:
                return [{"result": str(search_result)}]
        else:
            return [{"result": f"No results found for: {query}"}]
            
    except Exception as e:
        print(f"Search error: {str(e)}")
        return [{"error": f"Search failed: {str(e)}"}]

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
    """Direct Firecrawl API scraping implementation using proper Firecrawl methods."""
    
    # Input validation
    if not urls:
        return [{"error": "No URLs provided"}]
    if not queries:
        return [{"error": "No queries provided"}]
    
    # Limit concurrent requests to avoid overwhelming servers
    MAX_CONCURRENT = 5
    if len(urls) > MAX_CONCURRENT:
        urls = urls[:MAX_CONCURRENT]
    
    try:
        from firecrawl import Firecrawl
        from pydantic import BaseModel
        
        # Define the schema using Pydantic
        class QueryResponse(BaseModel):
            queries: str
            answer: str
        
        # Initialize Firecrawl client with default API key
        app = Firecrawl(api_key=os.getenv("FIRECRAWL_API_KEY", "fc-4e2dd3f9580f4c9094fd3ef5d2a02d97"))
        
        extract_prompt = (
            f"queries: {str(queries)}\n"
            "answer: answer with the information you get from the website. "
            "if cannot find answer, return 'answer not found'"
        )

        async def scrape_single_url(url: str) -> dict:
            """Scrape a single URL with error handling."""
            try:
                # Use Firecrawl scrape with JSON extraction
                result = app.scrape(
                    url,
                    formats=[{
                        "type": "json",
                        "schema": QueryResponse,
                        "prompt": extract_prompt
                    }],
                    only_main_content=True,
                    timeout=30000
                )
                
                if result and hasattr(result, 'json') and result.json:
                    return {
                        "url": url,
                        "status": "success",
                        "content": result.json
                    }
                else:
                    return {
                        "url": url,
                        "status": "error",
                        "error": "No content extracted"
                    }
                    
            except Exception as e:
                return {
                    "url": url,
                    "status": "error",
                    "error": str(e)
                }

        # Process URLs concurrently
        tasks = [scrape_single_url(url) for url in urls]
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
        return [{"error": f"Scraping setup failed: {str(e)}"}]

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
    