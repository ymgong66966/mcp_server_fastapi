import os
from firecrawl import Firecrawl
from pydantic import BaseModel

# Define the schema using Pydantic
class QueryResponse(BaseModel):
    queries: str
    answer: str

# domain = "https://www.homeinstead.com/"
# app = Firecrawl(api_key=os.getenv('FIRECRAWL_API_KEY', 'fc-a316f888b79549cfa9bf3e23a8ec6556'))
# url_list = app.map(domain, limit=50, sitemap="include")
# print(url_list)

app = Firecrawl(api_key=os.getenv("FIRECRAWL_API_KEY", "fc-a316f888b79549cfa9bf3e23a8ec6556"))
# search_result = app.search(sources=["web"], query="when is the birthdate of the president", limit=2)
# print(search_result)
url = "https://www.homeinstead.com/"
queries = ["what services do they offer?"]
extract_prompt = (
            f"queries: {str(queries)}\n"
            "answer: answer with the information you get from the website. "
            "if cannot find answer, return 'answer not found'"
        )
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

print(result.json)
# import requests

# url = "https://api.firecrawl.dev/v2/map"
# headers = {
#     "Content-Type": "application/json",
#     "Authorization": "Bearer fc-a316f888b79549cfa9bf3e23a8ec6556"  # replace with your actual Firecrawl API key
# }
# data = {
#     "url": "https://www.homeinstead.com/",
#     "search": "veteran benefits",
#     "limit": 20,
    
# }

# response = requests.post(url, headers=headers, json=data)

# # Print status and response JSON
# print("Status:", response.status_code)
# print("Response:", response.json())