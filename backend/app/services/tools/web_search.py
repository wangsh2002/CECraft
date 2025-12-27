import asyncio
from typing import List
from langchain_community.chat_models import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
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
    # 策略优化：使用 LLM 进行搜索词重写，替代简单的关键词拼接
    # 这能更精准地处理 "帮我查一下..." 等自然语言
    refined_query = await _optimize_query_with_llm(query)
    print(f"--- [Researcher] 原始问题: {query} | 优化后搜索词: {refined_query} ---")

    print(f"--- [Researcher] 开始联网搜索: {refined_query} ---")
    
    # 步骤 A: 调用 DuckDuckGo 获取 URL 列表
    # 增加 limit 数量，因为可能会有一些抓取失败
    urls = await _search_duckduckgo(refined_query, limit=5) 
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

async def _optimize_query_with_llm(query: str) -> str:
    """
    使用 LLM 将用户自然语言转化为搜索引擎友好的关键词查询
    """
    prompt = ChatPromptTemplate.from_template(
        """你是一个搜索专家。请将用户的自然语言问题转化为一个针对搜索引擎优化的关键词查询。
        
        原则：
        1. 去除无意义的词（如“帮我查一下”、“我想知道”）。
        2. 提取核心实体（如技术栈、职位、公司）。
        3. 如果是招聘相关，适当补充“面经”、“薪资”、“JD”、“任职要求”等高价值后缀。
        4. 保持简短，通常不超过 5 个关键词。
        
        用户问题: {query}
        
        优化后的搜索词 (仅输出一行文本):"""
    )
    chain = prompt | llm | StrOutputParser()
    try:
        return await chain.ainvoke({"query": query})
    except Exception as e:
        print(f"Query Optimization Failed: {e}")
        return query

async def _search_duckduckgo(query: str, limit: int = 3) -> List[str]:
    """
    私有函数：使用 DuckDuckGo 获取搜索结果链接
    """
    try:
        # DDGS 是同步库，为了不阻塞异步循环，我们在线程池中运行
        def run_search():
            with DDGS() as ddgs:
                # 策略优化：
                # 1. 增加搜索结果数量 (max_results=10)，然后手动过滤
                # 2. 优先选择包含 "blog", "article", "zhuanlan", "post" 等关键词的 URL
                # 3. 排除掉一些低质量的 SEO 农场或无法访问的站点
                results = list(ddgs.text(query, max_results=10))
                
                filtered_urls = []
                # 优先站点关键词
                priority_domains = ["zhihu.com", "juejin.cn", "csdn.net", "v2ex.com", "segmentfault.com", "cnblogs.com", "infoq.cn", "woshipm.com"]
                # 排除站点关键词
                exclude_domains = ["baidu.com", "so.com", "sogou.com", "google.com", "bing.com", "youtube.com", "bilibili.com"] # 排除搜索引擎自身或视频站

                # 第一轮：优先筛选高质量社区/博客
                for r in results:
                    url = r['href']
                    if any(d in url for d in priority_domains):
                        filtered_urls.append(url)
                
                # 第二轮：如果不够，补充其他非排除站点的结果
                if len(filtered_urls) < limit:
                    for r in results:
                        url = r['href']
                        if url not in filtered_urls and not any(d in url for d in exclude_domains):
                            filtered_urls.append(url)
                            if len(filtered_urls) >= limit:
                                break
                
                return filtered_urls[:limit]
        
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
            # 策略优化：伪装成真实浏览器 User-Agent，降低被反爬拦截的概率
            # 许多站点会拦截默认的 python-requests 或爬虫 UA
            custom_headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            # arun 是 crawl4ai 的核心异步方法
            # magic=True (如果支持) 可以尝试自动处理一些动态内容，这里保守起见只加 headers
            # bypass_cache=True 确保获取最新内容
            # 性能优化：增加 15 秒超时控制，防止单个慢站拖累整体
            result = await asyncio.wait_for(
                crawler.arun(url=url, headers=custom_headers, bypass_cache=True),
                timeout=15.0
            )
            
            if result.success:
                # 我们只需要 markdown 格式，且为了防爆 Token，截取前 6000 字符
                # 这里的逻辑是：通常重要信息都在文章开头，但 2000 可能太短了
                return f"来源URL: {url}\n内容摘要:\n{result.markdown[:6000]}..." 
            else:
                print(f"抓取失败 (Status {result.status_code}): {url}")
                return ""
        except asyncio.TimeoutError:
            print(f"抓取超时 (15s): {url}")
            return ""
        except Exception as e:
            print(f"抓取 {url} 异常: {e}")
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
    - **智能去噪**：用户搜索技术/岗位词（如 "AI Agent"）时，经常会出现无关领域的干扰结果（如“金融代理人”、“前端UI组件”）。请务必**识别并过滤**掉这些明显偏离核心语义的内容，只保留最相关、最硬核的信息。
    - 如果用户询问“岗位需求”或“招聘要求”，请务必提取具体的**硬性技能**（如Python, LangChain）、**软性技能**、**工作职责**、**经验要求**等细节。
    - 不要只给出笼统的总结（如“需要编程能力”），而要给出具体的描述（如“精通Python，熟悉异步编程”）。
    
    要求：
    1. **相关性第一**：如果搜索结果包含多个领域（例如“AI Agent”既有大模型智能体，又有金融中介），请优先保留**计算机/人工智能/大模型**领域的内容，除非用户明确问了其他领域。
    2. **去除噪音**：忽略广告、导航栏、无关的推荐列表。
    3. **细节优先**：优先保留具体的名词、工具名、技术栈和数据。
    4. **格式清晰**：使用 Markdown 列表整理关键点。
    5. **不要瞎编**：只能基于提供的【搜索结果】回答。
    6. **统一总结**：请将所有来源的信息**融合**在一起回答，不要按来源（如“来源1说...来源2说...”）分段，直接给出一份完整的综合报告。
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