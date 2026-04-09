import asyncio
from tools.web import LangchainWebSearchTool

async def main():
    tool = LangchainWebSearchTool()
    res = tool._run("latest local news Stafford Staffordshire UK", "latest local news for Stafford, Staffordshire")
    print(res)

asyncio.run(main())
