import asyncio
import sys
import os

# Add backend to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.tools.web_search import perform_web_search

async def main():
    query = "2024年 Python后端工程师 平均薪资"
    print(f"Testing search with query: {query}")
    try:
        result = await perform_web_search(query)
        print("\nSearch Result Summary:")
        print(result[:500] + "..." if len(result) > 500 else result)
    except Exception as e:
        print(f"Search failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
