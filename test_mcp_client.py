import asyncio
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession

async def main():
    params = StdioServerParameters(
        command="python",
        args=["-m", "invisible_playwright_mcp"]
    )
    async with stdio_client(params) as (read, write):
        session = ClientSession(read, write)
        await session.initialize()
        
        # List available tools
        tools = await session.list_tools()
        print("=== TOOLS ===")
        for t in tools.tools:
            print(f"  {t.name}: {t.description}")
        
        # Try browser_open
        print("\n=== BROWSER OPEN ===")
        result = await session.call_tool('browser_open', {'url': 'https://example.com'})
        print(f"Result: {result.content}")
        
        # Try browser_read_text
        print("\n=== BROWSER READ TEXT ===")
        result2 = await session.call_tool('browser_read_text', {})
        print(f"Result: {result2.content}")
        
        # Check for Example Domain
        if result2.content:
            text = result2.content[0].text if hasattr(result2.content[0], 'text') else str(result2.content[0])
            print(f"Text contains 'Example Domain': {'Example Domain' in text}")
        
        # browser_close
        print("\n=== BROWSER CLOSE ===")
        result3 = await session.call_tool('browser_close', {})
        print(f"Result: {result3.content}")

asyncio.run(main())