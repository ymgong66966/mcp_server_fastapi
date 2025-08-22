import asyncio
# from fastmcp import Client, FastMCP

# # In-memory server (ideal for testing)
# server = FastMCP("TestServer")
# client = Client(server)

# # HTTP server
# client = Client("https://example.com/mcp")

# # Local Python script
# # client = Client("my_mcp_server.py")

# async def main():
#     async with client:
#         # Basic server interaction
#         await client.ping()
        
#         # List available operations
#         tools = await client.list_tools()
#         resources = await client.list_resources()
#         prompts = await client.list_prompts()
        
#         # Execute operations
#         result = await client.call_tool("example_tool", {"param": "value"})
#         print(result)

# asyncio.run(main())


from fastmcp import Client

# Use LoadBalancer external URL from AWS ELB
client = Client("http://abcd9566cb3bc452b81b1bd3a1b11640-1476439698.us-east-2.elb.amazonaws.com/mcp/")
async def main():
    async with client:
        tools = await client.list_tools()
        print("Available tools:", tools)
        result = await client.call_tool("add", {"a": 5, "b": 3})
        print("Add result:", result)

asyncio.run(main())