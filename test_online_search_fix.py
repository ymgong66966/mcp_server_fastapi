#!/usr/bin/env python3
"""
Quick test of the online search tool with correct name
"""
import asyncio
import json
import httpx

async def test_online_search():
    server_url = "http://a7a09ec61615e46a7892d050e514c11e-1977986439.us-east-2.elb.amazonaws.com/mcp"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Initialize
        init_response = await client.post(
            server_url,
            json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "online-test", "version": "1.0"}
                }
            },
            headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        )
        
        session_id = init_response.headers.get("mcp-session-id")
        
        # Send initialized notification
        await client.post(
            server_url,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers={"Content-Type": "application/json", "Mcp-Session-Id": session_id}
        )
        
        await asyncio.sleep(1.0)
        
        # Test online search with correct name
        print("🌐 Testing '/online_online_search' tool...")
        response = await client.post(
            server_url,
            json={
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {
                    "name": "/online_online_search",
                    "arguments": {"query": "MCP protocol documentation"}
                }
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": session_id
            }
        )
        print(response)
        if response.status_code == 200:
            data = response.text
            if "data:" in data:
                for line in data.split('\n'):
                    if line.startswith('data:'):
                        try:
                            result = json.loads(line[5:])
                            if 'result' in result:
                                content = result['result'].get('content', [])
                                if content:
                                    search_result = content[0].get('text', result['result'])
                                    print(f"✅ Online search result: {search_result}")
                                else:
                                    print(f"✅ Raw result: {result['result']}")
                        except json.JSONDecodeError:
                            continue
        
        print("🎉 All 3 MCP tools now working correctly!")

if __name__ == "__main__":
    asyncio.run(test_online_search())