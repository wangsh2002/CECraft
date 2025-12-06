import os
import asyncio
import aiohttp
import time
from typing import List, Optional
from langchain_community.chat_models import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate
from crawl4ai import AsyncWebCrawler

# 复用配置
from app.core.config import settings

# ==========================================
# 1. 配置与初始化
# ==========================================
SAVE_DIR = "./data/resumes_crawled"
DEBUG_DIR = "./data/debug_raw"  # 新增调试目录
os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(DEBUG_DIR, exist_ok=True)

llm = ChatTongyi(
    model="qwen-plus", 
    dashscope_api_key=settings.DASHSCOPE_API_KEY,
    temperature=0.1
)

# ==========================================
# 2. 搜索与爬取
# ==========================================

async def _search_searxng(query: str, limit: int = 3) -> List[str]:
    params = {"q": query, "format": "json", "language": "zh-CN"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{settings.SEARXNG_BASE_URL}/search", params=params, timeout=10) as resp:
                if resp.status != 200:
                    print(f"[Search] 请求失败: {resp.status}")
                    return []
                data = await resp.json()
                # 放宽限制，不过滤 PDF 看看（虽然 crawl4ai 解析 PDF 能力有限，但先看看有没有链接）
                urls = [r["url"] for r in data.get("results", [])][:limit]
                print(f"[Search] 关键词 '{query}' 找到链接: {urls}")
                return urls
    except Exception as e:
        print(f"[Error] 搜索异常: {e}")
        return []

async def _crawl_raw_content(urls: List[str]) -> List[dict]:
    results_data = []
    
    print(f"[Crawl] 正在抓取 {len(urls)} 个链接...")
    async with AsyncWebCrawler(verbose=True) as crawler: # 开启 verbose 看底层日志
        for url in urls:
            try:
                # 尝试更激进的抓取配置
                # css_selector=None 表示抓取全文
                # word_count_threshold=10 忽略太短的
                result = await crawler.arun(url=url, bypass_cache=True, magic=True)
                
                if result.success:
                    content = result.markdown
                    print(f"  -> 成功抓取: {url} (长度: {len(content)})")
                    if len(content) < 100:
                        print(f"     [警告] 内容过短: {content}")
                    results_data.append({"url": url, "content": content})
                else:
                    print(f"  -> 抓取失败: {url} | 原因: {result.error_message}")
            except Exception as e:
                print(f"  -> 抓取异常: {url} | {e}")
    
    return results_data

# ==========================================
# 3. 清洗 (调试版：不跳过，强行提取)
# ==========================================

async def _clean_resume_data(raw_data: dict):
    url = raw_data['url']
    content = raw_data['content']
    
    # 【调试步骤 1】保存原始内容，看看是不是抓到了验证码或者空页面
    safe_hash = str(abs(hash(url)))
    debug_filename = os.path.join(DEBUG_DIR, f"raw_{safe_hash}.md")
    with open(debug_filename, "w", encoding="utf-8") as f:
        f.write(f"URL: {url}\n\n{content}")
    print(f"[Debug] 原始内容已保存至: {debug_filename}")

    # 如果内容太短，LLM 也没法清洗，直接返回
    if len(content) < 50:
        return None

    # 【调试步骤 2】修改 Prompt，不再允许 SKIP，要求尽可能提取
    system_prompt = """
    你是一个数据提取助手。你的任务是从网页内容中提取简历、职位描述或技能相关信息。
    
    【强制执行】：
    1. 即使内容包含大量噪音（广告、导航），也要尽力挖掘出相关的文本。
    2. 如果内容看起来像是一篇技术文章而不是简历，请提取文章中的核心技术点作为“技能树”。
    3. 如果实在找不到任何相关信息，请输出：“【分析失败】内容主题是：(这里简述内容主题)”。
    4. 不要输出代码块，直接输出 Markdown 文本。
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", f"URL: {url}\n\n内容:\n{content[:15000]}") # 喂更多内容
    ])
    
    chain = prompt | llm
    
    try:
        response = await chain.ainvoke({})
        cleaned_text = response.content.strip()
        
        # 只要 LLM 没报错，我们就保存，看看它输出了啥
        final_doc = f"---\nurl: {url}\ncrawled_at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n---\n\n{cleaned_text}"
        return final_doc
    except Exception as e:
        print(f"[Clean Error] LLM 处理失败: {e}")
        return None

# ==========================================
# 4. 主流程
# ==========================================

async def run_crawl_task(keywords: List[str]):
    for kw in keywords:
        print(f"\n=== 关键词: {kw} ===")
        urls = await _search_searxng(kw, limit=2)
        if not urls: continue
        
        raw_items = await _crawl_raw_content(urls)
        
        for item in raw_items:
            cleaned_doc = await _clean_resume_data(item)
            if cleaned_doc:
                filename = f"cleaned_{abs(hash(item['url']))}.md"
                filepath = os.path.join(SAVE_DIR, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(cleaned_doc)
                print(f"[Save] 结果已保存: {filepath}")

if __name__ == "__main__":
    # 换几个容易抓的词试试
    TARGET_KEYWORDS = [
        "程序员简历模板 site:github.com",  # Github 通常好抓
        "Java工程师 岗位职责",            # 招聘网站虽然难抓，但普通博客好抓
        "Python面试题总结"                # 这种文章也包含大量技能点
    ]
    
    asyncio.run(run_crawl_task(TARGET_KEYWORDS))