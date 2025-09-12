import asyncio
import aiohttp
import json
import os
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class GooglePlacesAPI:
    """Async Google Places API client for searching nearby places, text search, and geocoding."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.text_search_url = "https://places.googleapis.com/v1/places:searchText"
        self.geocoding_url = "https://maps.googleapis.com/maps/api/geocode/json"
    
    def extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from a website URL."""
        try:
            if not url:
                return None
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return None
    
    def enrich_places_with_domain(self, places: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich places data with extracted domain information."""
        enriched_places = []
        for place in places:
            enriched_place = place.copy()
            website_uri = place.get('websiteUri')
            if website_uri:
                domain = self.extract_domain(website_uri)
                enriched_place['domain'] = domain
            else:
                enriched_place['domain'] = None
            enriched_places.append(enriched_place)
        return enriched_places

    async def search_text(
        self,
        text_query: str,
        max_result_count: int = 10,
        field_mask: str = "places.displayName,places.formattedAddress,places.priceLevel,places.rating,places.location,places.websiteUri"
    ) -> Dict[str, Any]:
        """
        Search for places using text query with Google Places Text Search API.
        
        Args:
            text_query: Text query like "Spicy Vegetarian Food in Sydney, Australia"
            max_result_count: Maximum number of results (default: 10)
            field_mask: Fields to return in response
            
        Returns:
            Dict containing API response with places data
        """
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": field_mask
        }
        
        payload = {
            "textQuery": text_query,
            "maxResultCount": max_result_count
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.text_search_url,
                    headers=headers,
                    json=payload
                ) as response:
                    response.raise_for_status()
                    return await response.json()
            
        except aiohttp.ClientError as e:
            return {"error": f"API request failed: {str(e)}"}
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse response: {str(e)}"}

    async def search_text_with_websites(
        self,
        text_query: str,
        max_result_count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for places using text query and return enriched data with website domains.
        
        Args:
            text_query: Text query like "coffee shops in San Francisco"
            max_result_count: Maximum number of results (default: 10)
            
        Returns:
            List of enriched place dictionaries with domain information
        """
        result = await self.search_text(
            text_query=text_query,
            max_result_count=max_result_count
        )
        
        if "error" in result:
            return []
            
        places = result.get("places", [])
        return self.enrich_places_with_domain(places)

async def test_google_places_api():
    """Test function to demonstrate Google Places API functionality with website data."""
    
    # Get API key from environment variable
    api_key = "AIzaSyBkUXBC57tZH4xbPiLqqcuszmUH0VOfe8U"
    if not api_key:
        print("❌ Error: GOOGLE_MAPS_API_KEY environment variable not set")
        return
    
    # Initialize the API client
    google_api = GooglePlacesAPI(api_key)
    
    print("🚀 Testing Google Places API with Website Data")
    print("=" * 50)
    
    # Test 1: Search for coffee shops with website information
    print("\n☕ TEST 1: Coffee Shops in San Francisco")
    print("-" * 40)
    
    try:
        places = await google_api.search_text_with_websites(
            "coffee shops in San Francisco", 
            max_result_count=5
        )
        
        if places:
            for i, place in enumerate(places, 1):
                print(f"\n{i}. {place.get('displayName', {}).get('text', 'Unknown')}")
                print(f"   📍 Address: {place.get('formattedAddress', 'N/A')}")
                print(f"   ⭐ Rating: {place.get('rating', 'N/A')}")
                print(f"   🌐 Website: {place.get('websiteUri', 'N/A')}")
                print(f"   🔗 Domain: {place.get('domain', 'N/A')}")
        else:
            print("No results found")
            
    except Exception as e:
        print(f"❌ Error in coffee shop search: {e}")
    
    # Test 2: Search for restaurants with specific cuisine
    print("\n\n🍕 TEST 2: Italian Restaurants in New York")
    print("-" * 40)
    
    try:
        result = await google_api.search_text(
            "Italian restaurants in New York",
            max_result_count=3
        )
        
        if "error" not in result:
            places = result.get("places", [])
            enriched_places = google_api.enrich_places_with_domain(places)
            
            for i, place in enumerate(enriched_places, 1):
                print(f"\n{i}. {place.get('displayName', {}).get('text', 'Unknown')}")
                print(f"   📍 Address: {place.get('formattedAddress', 'N/A')}")
                print(f"   ⭐ Rating: {place.get('rating', 'N/A')}")
                print(f"   🌐 Website: {place.get('websiteUri', 'N/A')}")
                print(f"   🔗 Domain: {place.get('domain', 'N/A')}")
        else:
            print(f"❌ Error: {result['error']}")
            
    except Exception as e:
        print(f"❌ Error in restaurant search: {e}")
    
    # Test 3: Search for healthcare facilities
    print("\n\n🏥 TEST 3: Healthcare Facilities in Chicago")
    print("-" * 40)
    
    try:
        places = await google_api.search_text_with_websites(
            "hospitals and clinics in Chicago",
            max_result_count=3
        )
        
        if places:
            for i, place in enumerate(places, 1):
                print(f"\n{i}. {place.get('displayName', {}).get('text', 'Unknown')}")
                print(f"   📍 Address: {place.get('formattedAddress', 'N/A')}")
                print(f"   ⭐ Rating: {place.get('rating', 'N/A')}")
                print(f"   🌐 Website: {place.get('websiteUri', 'N/A')}")
                print(f"   🔗 Domain: {place.get('domain', 'N/A')}")
        else:
            print("No results found")
            
    except Exception as e:
        print(f"❌ Error in healthcare search: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Google Places API Test Complete!")

if __name__ == "__main__":
    asyncio.run(test_google_places_api())