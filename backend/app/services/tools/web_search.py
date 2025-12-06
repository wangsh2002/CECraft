import asyncio
from typing import List
from langchain_community.chat_models import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate
from crawl4ai import AsyncWebCrawler
from ddgs import DDGS

from app.core.config import settings

# ==========================================
# 1. 初始化模型 (用于最后的总结清洗)
# ==========================================
# 为了节省成本，这里建议使用 qwen-turbo 或 qwen-plus，不需要用 max
llm = ChatTongyi(
    model="qwen-turbo",
    dashscope_api_key=settings.DASHSCOPE_API_KEY,
    temperature=0.1
)

# ==========================================
# 2. 核心入口函数
# ==========================================
async def perform_web_search(query: str) -> str:
    """
    对外暴露的主函数：输入问题 -> 返回清洗后的 Markdown 摘要
    """
    print(f"--- [Researcher] 开始联网搜索: {query} ---")
    
    # 步骤 A: 调用 DuckDuckGo 获取 URL 列表
    urls = await _search_duckduckgo(query, limit=3) # 为了速度，我们先只看前3个
    if not urls:
        return "未找到相关网络搜索结果。"

    # 步骤 B: 并发抓取这些 URL 的内容
    print(f"--- [Researcher] 正在抓取 {len(urls)} 个网页... ---")
    raw_contents = await _crawl_concurrently(urls)

    # 步骤 C: 让 LLM 清洗并提取摘要
    print(f"--- [Researcher] 正在生成摘要... ---")
    summary = await _summarize_content(query, raw_contents)
    
    print(f"--- [Researcher] 搜索任务完成 ---")
    return summary

# ==========================================
# 3. 内部工具函数 (Helper Functions)
# ==========================================

async def _search_duckduckgo(query: str, limit: int = 3) -> List[str]:
    """
    私有函数：使用 DuckDuckGo 获取搜索结果链接
    """
    try:
        # DDGS 是同步库，为了不阻塞异步循环，我们在线程池中运行
        def run_search():
            with DDGS() as ddgs:
                # text() 方法返回一个生成器，我们需要将其转换为列表
                # max_results 参数控制返回结果数量
                return [r['href'] for r in ddgs.text(query, max_results=limit)]
        
        urls = await asyncio.to_thread(run_search)
        print(f"DuckDuckGo 返回链接: {urls}")
        return urls
    except Exception as e:
        print(f"DuckDuckGo 搜索异常: {str(e)}")
        return []

async def _crawl_concurrently(urls: List[str]) -> List[str]:
    """
    私有函数：使用 Crawl4AI 并发抓取多个 URL
    """
    contents = []
    
    # 定义单个抓取任务
    async def crawl_one(crawler, url):
        try:
            # arun 是 crawl4ai 的核心异步方法
            result = await crawler.arun(url=url)
            if result.success:
                # 我们只需要 markdown 格式，且为了防爆 Token，截取前 6000 字符
                # 这里的逻辑是：通常重要信息都在文章开头，但 2000 可能太短了
                return f"来源URL: {url}\n内容摘要:\n{result.markdown[:6000]}..." 
            else:
                return ""
        except Exception as e:
            print(f"抓取 {url} 失败: {e}")
            return ""

    # 启动 Crawl4AI 的上下文管理器
    async with AsyncWebCrawler(verbose=True) as crawler:
        # 创建所有任务
        tasks = [crawl_one(crawler, url) for url in urls]
        # asyncio.gather 让这些任务“同时”跑，而不是一个接一个跑
        results = await asyncio.gather(*tasks)
        
        # 过滤掉空的抓取结果
        contents = [r for r in results if r]

    return contents

async def _summarize_content(query: str, raw_contents: List[str]) -> str:
    """
    私有函数：将乱七八糟的抓取内容整合成一段干净的回答
    """
    if not raw_contents:
        return "无法抓取到网页内容。"

    # 拼接所有网页内容，中间用分割线隔开
    combined_text = "\n\n=== 下一篇文档 ===\n\n".join(raw_contents)

    # 构造 Prompt
    system_prompt = """
    你是一个专业的互联网信息情报员。
    你的任务是根据用户的问题，从给定的多篇网页抓取内容中，提取**尽可能详细**的信息。
    
    特别注意：
    - 如果用户询问“岗位需求”或“招聘要求”，请务必提取具体的**硬性技能**（如Python, LangChain）、**软性技能**、**工作职责**、**经验要求**等细节。
    - 不要只给出笼统的总结（如“需要编程能力”），而要给出具体的描述（如“精通Python，熟悉异步编程”）。
    - 如果原文包含具体的列表或要点，请尽量保留。
    
    要求：
    1. **去除噪音**：忽略广告、导航栏等无关信息。
    2. **细节优先**：优先保留具体的名词、工具名、技术栈和数据。
    3. **格式清晰**：使用 Markdown 列表整理关键点。
    4. **不要瞎编**：只能基于提供的【搜索结果】回答。
    """
    
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "用户问题：{query}\n\n【搜索结果】：\n{context}")
    ])

    # 调用 Chain
    chain = prompt_template | llm
    
    try:
        response = await chain.ainvoke({
            "query": query,
            "context": combined_text
        })
        return response.content
    except Exception as e:
        print(f"LLM 摘要生成失败: {e}")
        return "生成摘要时发生错误。"