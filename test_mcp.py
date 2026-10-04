import sys
sys.path.insert(0, r'C:\Users\ANL\Desktop\KAZEN_AI\.venv\Lib\site-packages')
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession
import asyncio

async def main():
    params = StdioServerParameters(
        command='python',
        args=['-m', 'invisible_playwright_mcp']
    )
    async with stdio_client(params) as (read, write):
        session = ClientSession(read, write)
        await session.initialize()
        tools = await session.list_tools()
        print('=== TOOLS ===')
        for t in tools.tools:
            print(f'  {t.name}: {t.description}')
        result = await session.call_tool('browser_open', {'url': 'https://example.com'})
        print(f'browser_open: {result.content}')
        result2 = await session.call_tool('browser_read_text', {})
        print(f'browser_read_text: {result2.content}')
        if result2.content:
            text = result2.content[0].text if hasattr(result2.content[0], 'text') else str(result2.content[0])
            has_domain = 'Example Domain' in text
            print(f'Contains Example Domain: {has_domain}')
        result3 = await session.call_tool('browser_close', {})
        print(f'browser_close: {result3.content}')

asyncio.run(main())