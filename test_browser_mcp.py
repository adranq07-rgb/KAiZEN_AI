import asyncio
import sys
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession

async def test_browser():
    # Start the invisible-playwright-mcp server and connect to it
    params = StdioServerParameters(
        command="python",
        args=[
            "-c",
            r'''
import sys
sys.path.insert(0, r"C:\Users\ANL\Desktop\KAZEN_AI\.venv\Lib\site-packages")
from invisible_playwright_mcp import __main__
__main__.main()
''']
    )
    
    try:
        async with stdio_client(params) as (read, write):
            session = ClientSession(read, write)
            await session.initialize()
            
            # List tools
            tools = await session.list_tools()
            print("=== Available Tools ===")
            for tool in tools.tools:
                print(f"  {tool.name}: {tool.description}")
            
            # browser_open
            print("\n>>> browser_open https://example.com")
            result = await session.call_tool('browser_open', {'url': 'https://example.com'})
            print(f"browser_open result: {result.content}")
            
            # browser_read_text
            print("\n>>> browser_read_text")
            result2 = await session.call_tool('browser_read_text', {})
            print(f"browser_read_text result: {result2.content}")
            
            # Look for "Example Domain" in the text
            text = result2.content[0].text if result2.content else ""
            has_example = "Example Domain" in text
            print(f"\n>>> Example Domain found: {has_example}")
            
            # browser_close
            print("\n>>> browser_close")
            result3 = await session.call_tool('browser_close', {})
            print(f"browser_close result: {result3.content}")
            
            print("\n=== ALL TESTS COMPLETE ===")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test_browser())