import aiohttp
import json
from typing import Dict, Any, List, Optional

class GooglePlacesAPI:
    """Async Google Places API client for searching nearby places, text search, and geocoding."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.text_search_url = "https://places.googleapis.com/v1/places:searchText"
        self.geocoding_url = "https://maps.googleapis.com/maps/api/geocode/json"
    
    
    async def search_text(
        self,
        text_query: str,
        max_result_count: int = 10,
        field_mask: str = "places.displayName,places.formattedAddress,places.priceLevel,places.rating,places.location"
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
    
    async def search_restaurants_by_text(
        self,
        location: str,
        location_query: str = "",
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Convenience method to search for restaurants using text query.
        
        Args:
            location: Location like "Sydney, Australia" or "New York"
            location_type: Optional cuisine type like "Spicy Vegetarian", "Italian", etc.
            max_results: Maximum number of results
            
        Returns:
            List of restaurant data dictionaries
        """
        if location_query:
            query = f"{location_query} in {location}"
        else:
            query = f"restaurants in {location}"
            
        result = await self.search_text(
            text_query=query,
            max_result_count=max_results
        )
        
        if "error" in result:
            return []
            
        return result.get("places", [])
    
    async def geocode_address(self, address: str) -> Optional[tuple]:
        """
        Geocode an address to coordinates using Google Maps Geocoding API.
        
        Args:
            address: Address to geocode
        
        Returns:
            Tuple of (latitude, longitude) or None if geocoding fails
        """
        params = {
            "address": address,
            "key": self.api_key
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.geocoding_url, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    if data["status"] == "OK":
                        lat = data["results"][0]["geometry"]["location"]["lat"]
                        lng = data["results"][0]["geometry"]["location"]["lng"]
                        return lat, lng
                    else:
                        return None
            
        except aiohttp.ClientError as e:
            return None