import asyncio
import time
import sys
import os
import argparse
import aiohttp

# 将 backend 目录添加到 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from app.core.config import settings
# 导入内部函数以便分步测试
from app.services.tools.web_search import (
    _optimize_query_with_llm,
    _search_duckduckgo,
    _crawl_concurrently,
    _summarize_content,
    _perform_bocha_search
)

async def test_duckduckgo_flow(query, refined_query):
    print(f"\n=== 测试 DuckDuckGo + Jina Reader 流程 ===")
    
    # 2. 搜索
    print("\n[2] 正在调用搜索引擎 (DuckDuckGo)...")
    t2 = time.time()
    search_results = await _search_duckduckgo(refined_query, limit=3)
    t3 = time.time()
    search_time = t3 - t2
    print(f"✅ 搜索引擎耗时: {search_time:.2f}s")
    print(f"   找到结果: {len(search_results)} 条")
    
    if not search_results:
        print("❌ 未找到结果，终止测试")
        return None

    urls = [r['href'] for r in search_results]
    
    # 3. 抓取
    print(f"\n[3] 正在抓取 {len(urls)} 个网页 (Jina Reader)...")
    t4 = time.time()
    crawled_contents = await _crawl_concurrently(urls)
    t5 = time.time()
    crawl_time = t5 - t4
    print(f"✅ 网页抓取耗时: {crawl_time:.2f}s")
    
    # 混合策略处理
    final_contents = []
    for i, content in enumerate(crawled_contents):
        if content and "Warning: Target URL returned error" not in content:
            final_contents.append(content)
        else:
            # Fallback to snippet
            snippet = search_results[i].get('body', '')
            title = search_results[i].get('title', '')
            url = search_results[i].get('href', '')
            if snippet:
                print(f"   ⚠️ [Fallback] 使用 Snippet 替代抓取失败: {url}")
                final_contents.append(f"来源URL: {url}\n标题: {title}\n内容摘要(Snippet): {snippet}")
    
    # 4. 总结
    print("\n[4] 正在生成 LLM 总结...")
    t6 = time.time()
    summary = await _summarize_content(query, final_contents)
    t7 = time.time()
    summary_time = t7 - t6
    print(f"✅ LLM总结耗时: {summary_time:.2f}s")
    
    return {
        "search": search_time,
        "crawl": crawl_time,
        "summary": summary_time,
        "result": summary
    }

async def test_bocha_flow(query, refined_query):
    print(f"\n=== 测试 Bocha Web Search 流程 (分步计时) ===")
    
    if not settings.BOCHA_API_KEY:
        print("❌ 未配置 BOCHA_API_KEY，请先在 .env 中配置。")
        return None

    # 1. 调用 Bocha API (搜索+抓取)
    print("\n[2] 正在调用 Bocha API (搜索+抓取)...")
    t2 = time.time()
    
    # --- 手动执行 Bocha 请求逻辑以分离计时 ---
    url = "https://api.bochaai.com/v1/web-search"
    headers = {
        "Authorization": f"Bearer {settings.BOCHA_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "query": refined_query,
        "freshness": "noLimit",
        "summary": True,
        "count": 8
    }
    
    contents = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=10) as response:
                if response.status != 200:
                    print(f"Bocha API Error: {response.status}")
                    return None
                
                data = await response.json()
                # 解析逻辑同 _perform_bocha_search
                if "data" in data and isinstance(data["data"], dict) and "webPages" in data["data"]:
                    web_pages = data["data"]["webPages"].get("value", [])
                else:
                    web_pages = data.get("webPages", {}).get("value", [])
                
                for page in web_pages:
                    title = page.get("name", "无标题")
                    url_link = page.get("url", "")
                    summary = page.get("summary") or page.get("snippet", "")
                    if summary:
                        contents.append(f"来源URL: {url_link}\n标题: {title}\n内容摘要:\n{summary}")
                        
    except Exception as e:
        print(f"Bocha Request Failed: {e}")
        return None
        
    t3 = time.time()
    bocha_api_time = t3 - t2
    print(f"✅ Bocha API 耗时: {bocha_api_time:.2f}s")
    print(f"   获取到 {len(contents)} 条有效摘要")

    # 2. 调用 LLM 总结
    print("\n[3] 正在生成 LLM 总结 (本地模型)...")
    t4 = time.time()
    summary_result = await _summarize_content(query, contents)
    t5 = time.time()
    summary_time = t5 - t4
    print(f"✅ LLM总结耗时: {summary_time:.2f}s")
    
    return {
        "bocha_api": bocha_api_time,
        "summary": summary_time,
        "result": summary_result
    }

async def test_speed():
    parser = argparse.ArgumentParser(description="Test Web Search Speed")
    parser.add_argument("--provider", choices=["duckduckgo", "bocha"], default="duckduckgo", help="Search provider to test")
    args = parser.parse_args()

    query = "2024年大模型算法工程师面试题"
    print(f"--- 开始测试联网搜索速度 ---")
    print(f"模式: {args.provider}")
    print(f"查询词: {query}")
    
    total_start = time.time()
    
    # 1. 优化查询 (公共步骤)
    print("\n[1] 正在优化查询...")
    t0 = time.time()
    refined_query = await _optimize_query_with_llm(query)
    t1 = time.time()
    optimize_time = t1 - t0
    print(f"✅ 查询优化耗时: {optimize_time:.2f}s")
    print(f"   优化后: {refined_query}")
    
    stats = None
    if args.provider == "duckduckgo":
        stats = await test_duckduckgo_flow(query, refined_query)
    else:
        # 先进行 debug
        # await debug_bocha_raw(refined_query)
        stats = await test_bocha_flow(query, refined_query)
        
    total_end = time.time()
    
    if stats:
        print(f"\n{'='*30}")
        print(f"📊 性能统计报告 ({args.provider})")
        print(f"{'='*30}")
        print(f"1. 查询优化: {optimize_time:.2f}s")
        
        if args.provider == "duckduckgo":
            print(f"2. 搜索耗时: {stats['search']:.2f}s")
            print(f"3. 抓取耗时: {stats['crawl']:.2f}s")
            print(f"4. 总结耗时: {stats['summary']:.2f}s")
        else:
            print(f"2. Bocha API耗时: {stats['bocha_api']:.2f}s (搜索+抓取)")
            print(f"3. LLM总结耗时:   {stats['summary']:.2f}s")
            
        print(f"{'-'*30}")
        print(f"🚀 总耗时:   {total_end - total_start:.2f}s")
        print(f"{'='*30}")
        
        print(f"\n[结果预览]\n{stats['result'][:300]}...")

if __name__ == "__main__":
    asyncio.run(test_speed())
