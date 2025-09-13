import requests
import json
import asyncio
from typing import Dict, Any, Optional
import os
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
            print(result)
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

async def main():
    """Main function to test different URLs and search terms."""
    
    # Test cases
    test_cases = [
        {
            "url": "comfortkeepers.com",
            "search_queries":[ "veteran benefits, LA", "veteran benefits, LA" ],
        },
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"TEST {i}: {test_case['url']}")
        print(f"{'='*60}")
        
        result = await website_map(
            url=test_case["url"],
            search_queries=test_case["search_queries"],
        )
        
        if result:
            print(f"✅ Test {i} completed successfully")
            print(result)
        else:
            print(f"❌ Test {i} failed")
        

if __name__ == "__main__":
    asyncio.run(main())