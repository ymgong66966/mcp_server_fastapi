import aiohttp
import json
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
import os
from loguru import logger

class GooglePlacesAPI:
    """Async Google Places API client for searching nearby places, text search, and geocoding."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.text_search_url = "https://places.googleapis.com/v1/places:searchText"
        self.geocoding_url = "https://maps.googleapis.com/maps/api/geocode/json"
        self.prompt = """
        You are a url parser for generating proper root urls for the firecrawl web_map funtion, where it smartly converses the subwebsites of a url. Your input is the url provided about something, the problem is that it can be too specific to be the root url used for web_map. You should know that the root url does not always mean the domain of the input url. For example, for the input url: 
https://www.homeinstead.com/home-care/usa/ca/san-francisco/220/?utm_source=google&utm_medium=organic&utm_campaign=google_organic_businesslisting_y  . you actually need to keep the url up to 
https://www.homeinstead.com/home-care/usa/ca/san-francisco Because it contains the geo-location of the url, which is useful information. But a lot of other times, you can just extract the web domain. Only the geo-location is important information to you.

Make sure that you output is json format: {{"extracted_url":"the url you extacted"}}. Do not include any other text like "json", "output" than the json output.

Here is your input url: {url}
        """
    
    def extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from a website URL."""
        try:
            print(url, "url")
            logger.info(url)
            if not url:
                return None
            llm = ChatOpenAI(
                temperature=0.1,
                api_key=os.getenv("OPENAI_API_KEY"),
                model="gpt-4.1"
            )
            prompt = PromptTemplate.from_template(self.prompt)
            chain = prompt | llm
            result = chain.invoke({"url": url})
            logger.info(result)
            json_result = json.loads(result.content)
            return json_result["extracted_url"]
        except Exception as e:
            return str(e)
    
    def enrich_places_with_domain(self, places: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich places data with extracted domain information."""
        enriched_places = []
        for place in places:
            enriched_place = place.copy()
            print(enriched_place, "place")
            website_uri = place.get('websiteUri')
            if website_uri:
                domain = self.extract_domain(website_uri)
                print(domain, "domain")
                enriched_place['domain'] = domain
            else:
                enriched_place['domain'] = None
            enriched_places.append(enriched_place)
        return enriched_places
    
    async def search_text(
        self,
        text_query: str,
        max_result_count: int = 3,
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
        max_result_count: int = 3
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
    
    async def search_restaurants_by_text(
        self,
        location: str,
        location_query: str = "",
        max_results: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Convenience method to search for restaurants using text query.
        
        Args:
            location: Location like "Sydney, Australia" or "New York"
            location_type: Optional cuisine type like "Spicy Vegetarian", "Italian", etc.
            max_results: Maximum number of results
            
        Returns:
            List of restaurant data dictionaries with website domains
        """
        if location_query:
            query = f"{location_query} in {location}"
        else:
            query = f"restaurants in {location}"
            
        result = await self.search_text(
            text_query=query,
            max_result_count=3
        )
        
        if "error" in result:
            return []
            
        places = result.get("places", [])

        return self.enrich_places_with_domain(places)
    
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