import asyncio
import json
import os
import requests
import httpx
from typing import List, Dict, Any, Optional
from fastmcp import FastMCP
# from web_map_zilliz_trie import zilliz_url_trie
from google_maps_api import GooglePlacesAPI
from dotenv import load_dotenv
from loguru import logger
load_dotenv()
online_mcp = FastMCP(name="online-search-mcp")

@online_mcp.tool(
        name="general_online_search_with_one_query",           # Custom tool name for the LLM
    description="""get general information from the internet about something asked by user. Best for: quick one-off Q&A about something. It is like someone wants you to search on google for them about something they don't have knowledge of. For exmaple: "What is respite care?", "What is a power of attorney?", "What is Medicaid?", "Define hospice care." etc. You can use this tool to get general information about something.

Not recommended for: when the user is asking for some specific information about a website or company. In this case you should use website_map tool first to get the urls of interest. The only exception is when the website_map or scrape_multiple_websites_after_website_map tools didn't return meaningful results. This tool can be used as the last resort in that case.
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
    description="""Get information from a list of urls about a list of queries. The input: a list of urls (strings) and a list of queries (strings). The output: a list of dictionaries (each dictionary contains the "queries" (string), the "answer" (string)). Best for: When you know which websites/urls you are interested in and want to dive deep into these websites and scrape information about a certain topic. When you are using this tool, you should input a list of the urls you think are of interest from the context or previous tools, and a list of queries you want to scrape information about. Make sure your queries are super relevant to the user intent and concise, otherwise you will be punished harshly. 

Not recommended for: when you only have a web domain or company front web page and still don't know which exact urls are of interest to you. In this case you should use website_map tool first to get the urls of interest.
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
            if result["status"] != "success":
                processed_results.append({
                    "url": urls[i],
                    "status": "error",
                    "error": f"Task failed: {str(result)}"
                })
            else:
                if "answer not found" not in result["content"]["answer"].lower():
                    processed_results.append(result)
        
        return processed_results
        
    except Exception as e:
        return [{"error": f"Scraping setup failed: {str(e)}"}]

@online_mcp.tool(name="website_map",           # Custom tool name for the LLM
    description="""Get relevant urls of a web domain about something asked by user. Best for: Finding specific information across multiple websites, when you don't know which website has the information. When you need the most relevant content for a query. 
    Example use case: a user asks follow-up questions about an in-home care agency which we have the website of. The input of the tool are the domain of that website as a string and a list of short queries that contain the user's intention and the city/area of interest. The output of the tool is a list of dictionaries (each dictionary contains the url, the title of the page, and the description of the page). If you think the description of the page is not informative enough, you can then use the urls as the input of the scrape_multiple_websites_after_website_map tool.
    
    IMPORTANT NOTES about the list of queries: 
    the list cannot have more than 3 query strings. Each query string should be short and concise. For example, if user asks about "can you check if this company has services for older adults with dementia?" and from the previous messages or context, we know that the user is interested in the city of oak park, Chicago, then the list of queries should be ["dementia services, Oak Park, Chicago", "Alzheimer services, Oak Park, Chicago"]. You will be punished if the list has more than 3 query strings or if the query strings are not short and informative.

Not recommended for: When you already know which urls to scrape and need comprehensive coverage of these urls (use scrape_multiple_websites_after_website_map tool)

""", # Custom description
    tags={ "online search"})
async def website_map(
    url: str = "https://firecrawl.dev",
    search_queries: list[str] = ["docs"],
) -> list[dict]:
    """The purpose of this function is to retrieve relevant information from a website based on a user's query. The function takes a web domain and a list of queries as input and returns a list of relevant URLs."""
    
    # API endpoint
    limit = 3
    sitemap = "include"
    api_key = os.getenv("FIRECRAWL_API_KEY", "fc-a316f888b79549cfa9bf3e23a8ec6556")
    endpoint = "https://api.firecrawl.dev/v2/map"
    
    # Headers
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    
    # Request payload with rate limiting
    result_urls = set()
    result_ls = []

    for i, search in enumerate(search_queries):
        # Add delay between internal API calls to prevent 429 errors
        if i > 0:  # No delay before first call
            delay = 2.0  # Match LangGraph's rate limiting strategy
            print(f"⏳ Internal rate limiting: waiting {delay}s before next Firecrawl API call")
            await asyncio.sleep(delay)

        payload = {
            "url": url,
            "search": search,
            "limit": limit,
            "sitemap": sitemap
        }

        try:
            print(f"🔍 Making Firecrawl API call {i+1}/{len(search_queries)} for query: '{search}'")

            # Make the POST request using httpx for async compatibility
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=payload
                )
                logger.info(response)

                # Check if request was successful
                if response.status_code == 200:
                    # Parse JSON response
                    result = response.json()
                    for link in result.get('links', []):
                        if link['url'] not in result_urls:
                            result_urls.add(link['url'])
                            result_ls.append(link)
                    print(f"✅ Successfully processed query '{search}' - found {len(result.get('links', []))} links")

                elif response.status_code == 429:
                    print(f"🚫 Rate limited (429) for query '{search}' - skipping this query")
                    # Continue with next query instead of failing entire function
                    continue
                else:
                    print(f"⚠️ API returned status {response.status_code} for query '{search}' - skipping")
                    continue

        except httpx.RequestError as e:
            print(f"❌ Request Error for query '{search}': {e}")
            # Continue with next query instead of failing entire function
            continue
        except json.JSONDecodeError as e:
            print(f"❌ JSON Decode Error for query '{search}': {e}")
            print(f"Raw response: {response.text}")
            continue
        except Exception as e:
            print(f"❌ Unexpected Error for query '{search}': {e}")
            continue
    
    return result_ls

@online_mcp.tool(name="google_places_search")
async def google_places_search(location: str, location_query: str = "") -> list[dict]:
    api = GooglePlacesAPI(api_key=os.getenv("GOOGLE_PLACES_API_KEY", "AIzaSyBkUXBC57tZH4xbPiLqqcuszmUH0VOfe8U"))
    results = await api.search_restaurants_by_text(location, location_query)
    return results
    
# async def website_map(domain: str, query: List[str]):
#     """The purpose of this function is to retrieve relevant information from a website based on a user's query. The function takes a web domain and a list of queries as input and returns a list of relevant URLs."""
#     print(domain, query, "domain and query")
#     relevant_urls = await zilliz_url_trie(domain, query)
#     return relevant_urls