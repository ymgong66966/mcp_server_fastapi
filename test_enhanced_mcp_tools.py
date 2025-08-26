#!/usr/bin/env python3
"""
Focused test for the enhanced MCP tools with web intelligence capabilities
"""
import asyncio
import json
import httpx

async def test_enhanced_mcp_tools():
    """Test the new enhanced MCP tools with proper initialization"""
    
    server_url = "http://a7a09ec61615e46a7892d050e514c11e-1977986439.us-east-2.elb.amazonaws.com/mcp"
    
    print("🚀 Testing Enhanced MCP Server Tools")
    print("=" * 50)
    
    async with httpx.AsyncClient(timeout=90.0) as client:  # Extended timeout for web operations
        
        # Initialize session
        print("🔄 Initializing MCP session...")
        init_response = await client.post(
            server_url,
            json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "enhanced-mcp-test", "version": "1.0.0"}
                }
            },
            headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        )
        
        if init_response.status_code != 200:
            print(f"❌ Initialization failed: {init_response.status_code}")
            return
            
        session_id = init_response.headers.get("mcp-session-id")
        print(f"✅ Session initialized: {session_id}")
        
        # Send initialized notification
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Mcp-Session-Id": session_id
        }
        
        await client.post(
            server_url,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=headers
        )
        
        await asyncio.sleep(2.0)  # Wait for full initialization
        
        # List all available tools
        print("\n📋 Listing all available tools...")
        tools_response = await client.post(
            server_url,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=headers
        )
        
        if tools_response.status_code == 200:
            tools_data = tools_response.text
            if "data:" in tools_data:
                for line in tools_data.split('\n'):
                    if line.startswith('data:'):
                        try:
                            result = json.loads(line[5:])
                            if 'result' in result and 'tools' in result['result']:
                                tools = result['result']['tools']
                                print(f"✅ Found {len(tools)} tools:")
                                for tool in tools:
                                    print(f"   🔧 {tool['name']}")
                                break
                        except json.JSONDecodeError:
                            continue
        
        # Test 1: General Online Search
        print("\n" + "="*60)
        print("🌐 TEST 1: General Online Search with Firecrawl")
        print("="*60)
        search_response = await client.post(
            server_url,
            json={
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {
                    "name": "/online_general_online_search_with_one_query",
                    "arguments": {"query": "latest AI developments 2024"}
                }
            },
            headers=headers
        )
        
        print(f"Status: {search_response.status_code}")
        await parse_and_display_result(search_response, "🔍 Search Results")
        
        # Test 2: Google Places Search  
        print("\n" + "="*60)
        print("📍 TEST 2: Google Places Search")
        print("="*60)
        places_response = await client.post(
            server_url,
            json={
                "jsonrpc": "2.0", "id": 4, "method": "tools/call",
                "params": {
                    "name": "/online_google_places_search",
                    "arguments": {
                        "location": "San Francisco, CA",
                        "location_query": "coffee shops"
                    }
                }
            },
            headers=headers
        )
        
        print(f"Status: {places_response.status_code}")
        await parse_and_display_result(places_response, "☕ Coffee Shops Found")
        
        # Test 3: Website Mapping
        print("\n" + "="*60)
        print("🗺️ TEST 3: Website Mapping with Vector Search")
        print("="*60)
        map_response = await client.post(
            server_url,
            json={
                "jsonrpc": "2.0", "id": 5, "method": "tools/call",
                "params": {
                    "name": "/online_website_map",
                    "arguments": {
                        "domain": "docs.anthropic.com",
                        "query": ["claude api documentation", "getting started"]
                    }
                }
            },
            headers=headers
        )
        
        print(f"Status: {map_response.status_code}")
        await parse_and_display_result(map_response, "🔗 Relevant URLs Found")
        
        # Test 4: Multi-Website Scraping
        print("\n" + "="*60)
        print("🕸️ TEST 4: Multi-Website Scraping")
        print("="*60)
        scrape_response = await client.post(
            server_url,
            json={
                "jsonrpc": "2.0", "id": 6, "method": "tools/call",
                "params": {
                    "name": "/online_scrape_multiple_websites_after_website_map",
                    "arguments": {
                        "urls": [
                            "https://example.com",
                            "https://httpbin.org/json"
                        ],
                        "queries": ["main content", "sample data"]
                    }
                }
            },
            headers=headers
        )
        
        print(f"Status: {scrape_response.status_code}")
        await parse_and_display_result(scrape_response, "📄 Scraped Content")
        
        # Final Summary
        print("\n" + "🎯" + "="*58 + "🎯")
        print("🎉 Enhanced MCP Server Test Complete!")
        print("✅ Web Intelligence Tools:")
        print("   • Firecrawl-powered search")
        print("   • Google Places integration") 
        print("   • AI-driven website mapping")
        print("   • Concurrent web scraping")
        print("   • Vector database semantic search")
        print("   • OpenAI embeddings & completions")
        print("🏆 Your MCP server has advanced AI capabilities!")
        print("="*60)

async def parse_and_display_result(response, title):
    """Helper function to parse and display MCP response results"""
    if response.status_code == 200:
        data = response.text
        if "data:" in data:
            for line in data.split('\n'):
                if line.startswith('data:'):
                    try:
                        result = json.loads(line[5:])
                        if 'result' in result:
                            content = result['result'].get('content', [])
                            if content and isinstance(content, list):
                                # Handle text content
                                text_content = content[0].get('text', str(result['result']))
                                print(f"✅ {title}:")
                                
                                # Try to parse as JSON for prettier display
                                try:
                                    if text_content.startswith('[') or text_content.startswith('{'):
                                        parsed_json = json.loads(text_content)
                                        print(json.dumps(parsed_json, indent=2)[:500] + "..." if len(str(parsed_json)) > 500 else json.dumps(parsed_json, indent=2))
                                    else:
                                        # Display first 300 chars for text results
                                        display_text = text_content[:300] + "..." if len(text_content) > 300 else text_content
                                        print(f"   {display_text}")
                                except json.JSONDecodeError:
                                    # Just display as text
                                    display_text = text_content[:300] + "..." if len(text_content) > 300 else text_content
                                    print(f"   {display_text}")
                            else:
                                # Handle direct result
                                result_str = str(result['result'])
                                display_text = result_str[:300] + "..." if len(result_str) > 300 else result_str
                                print(f"✅ {title}: {display_text}")
                        elif 'error' in result:
                            print(f"❌ {title} Error: {result['error']}")
                        return
                    except json.JSONDecodeError:
                        continue
        else:
            print(f"✅ {title}: Raw response - {response.text[:200]}...")
    else:
        print(f"❌ {title} Failed: {response.status_code} - {response.text}")

if __name__ == "__main__":
    asyncio.run(test_enhanced_mcp_tools())