import requests
import json
import asyncio
from typing import Dict, Any, Optional
import os
from langchain_core.messages import ToolMessage
import uuid
from google_maps_api import GooglePlacesAPI
async def website_map(
    url: str = "https://firecrawl.dev",
    search_queries: list[str] = ["docs"],
) -> Optional[Dict[str, Any]]:
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
    
    # Request payload
    result_urls = set()
    result_ls = []
    for search in search_queries:
        payload = {
            "url": url,
            "search": search,
            "limit": limit,
            "sitemap": sitemap
    }
    
        try:
            
            # Make the POST request
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            # Check if request was successful
            response.raise_for_status()
            
            # Parse JSON response
            result = response.json()
            for link in result['links']:
                if link['url'] not in result_urls:
                    result_urls.add(link['url'])
                    result_ls.append(link)
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Request Error: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ JSON Decode Error: {e}")
            print(f"Raw response: {response.text}")
            return None
        except Exception as e:
            print(f"❌ Unexpected Error: {e}")
            return None
    
    return result_ls


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

async def execute_single_tool(tool_call):
    try:

        observation = await website_map(tool_call["args"]["url"], tool_call["args"]["search_queries"])
        
        # Create enhanced, contextual tool message
        formatted_result = observation
        return ToolMessage(
            content=f"""🔧 TOOL EXECUTED:
📝 Called with parameters: {json.dumps(tool_call["args"], indent=2)}

{formatted_result}

---""",
            tool_call_id=str(uuid.uuid4())
        )
        
    except Exception as e:
        return ToolMessage(
            content=f"""❌ TOOL ERROR:
📝 Called with parameters: {json.dumps(tool_call.get("args", {}), indent=2)}
🚨 Error: {str(e)}

Please try a different approach or tool.
---""",
            tool_call_id=str(uuid.uuid4())
        )


async def main():
    # """Main function to test different URLs and search terms."""
    
    # # Test cases
    # test_cases = [
    #     {
    #         "url": "comfortkeepers.com",
    #         "search_queries":[ "veteran benefits, LA", "veteran benefits, LA" ],
    #     },
    # ]
    
    # for i, test_case in enumerate(test_cases, 1):
    #     print(f"\n{'='*60}")
    #     print(f"TEST {i}: {test_case['url']}")
    #     print(f"{'='*60}")
        
    #     result = await website_map(
    #         url=test_case["url"],
    #         search_queries=test_case["search_queries"],
    #     )
        
    #     if result:
    #         print(f"✅ Test {i} completed successfully")
    #         print(result)
    #     else:
    #         print(f"❌ Test {i} failed")
    # test_case_2 = {
    #     "urls": ["https://www.comfortkeepers.com/offices/california/los-angeles/areas-served/area/inglewood/service/alzheimer's-and-dementia-care/"],
    #     "queries": ["how do they support dementia people"],
    # }
    # result = await scrape_multiple_websites_implementation(test_case_2["urls"], test_case_2["queries"])
    # print(result)


    
    # Execute all tool calls concurrently
    # tool_calls = [{"args": {"url": "https://www.homeinstead.com/home-care/usa/ca/san-francisco",
    # "search_queries": [
    #   "dementia care",
    #   "Alzheimer's care",
    # ]}}]
    # tool_messages = await asyncio.gather(*[execute_single_tool(tool_call) for tool_call in tool_calls])
    
    # # Merge all tool messages into one with separators
    # merged_content = "\n\n" + "="*80 + "\n🔗 MERGED TOOL RESULTS\n" + "="*80 + "\n\n"
    # for i, tool_message in enumerate(tool_messages, 1):
    #     merged_content += f"📋 RESULT {i}:\n" + "-"*40 + "\n"
    #     merged_content += tool_message.content + "\n\n"
    
    # final_message = ToolMessage(
    #     content=merged_content,
    #     tool_call_id=str(uuid.uuid4())
    # )
    
    # print(final_message.content)

    api = GooglePlacesAPI(api_key=os.getenv("GOOGLE_PLACES_API_KEY", "AIzaSyBkUXBC57tZH4xbPiLqqcuszmUH0VOfe8U"))
    results = await api.search_restaurants_by_text("Los Angeles, CA", "dementia care")
    print(results)


if __name__ == "__main__":
    asyncio.run(main())