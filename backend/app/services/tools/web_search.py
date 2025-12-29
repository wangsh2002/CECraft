import asyncio
from typing import List
import aiohttp
from langchain_community.chat_models import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from ddgs import DDGS

from app.core.config import settings

# ==========================================
# 1. 初始化模型 (用于最后的总结清洗)
# ==========================================
# 为了节省成本，这里建议使用 qwen-turbo 或 qwen-plus，不需要用 max
llm = ChatOpenAI(
    model=settings.LLM_MODEL_LITE,
    openai_api_key=settings.OPENAI_API_KEY,
    openai_api_base=settings.OPENAI_API_BASE,
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

    # === 路由逻辑 ===
    provider = settings.SEARCH_PROVIDER.lower()
    
    if provider == "bocha":
        if not settings.BOCHA_API_KEY:
            print("❌ [Config] 未配置 BOCHA_API_KEY，请检查 .env 文件。")
            return "配置错误：未设置 BOCHA_API_KEY。"
        return await _perform_bocha_search(refined_query)

    # === 默认 DuckDuckGo 逻辑 ===
    print(f"--- [Researcher] 开始联网搜索 (DuckDuckGo): {refined_query} ---")
    
    # 步骤 A: 调用 DuckDuckGo 获取 URL 列表
    # 优化：减少 limit 到 3，提高响应速度
    search_results = await _search_duckduckgo(refined_query, limit=3) 
    if not search_results:
        return "未找到相关网络搜索结果。"

    urls = [r['href'] for r in search_results]

    # 步骤 B: 并发抓取这些 URL 的内容
    print(f"--- [Researcher] 正在抓取 {len(urls)} 个网页... ---")
    crawled_contents = await _crawl_concurrently(urls)

    # 步骤 C: 混合策略 (Crawl 失败则使用 Snippet)
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
                print(f"--- [Fallback] 使用 Snippet 替代抓取失败: {url} ---")
                final_contents.append(f"来源URL: {url}\n标题: {title}\n内容摘要(Snippet): {snippet}")

    # 步骤 D: 让 LLM 清洗并提取摘要
    print(f"--- [Researcher] 正在生成摘要... ---")
    summary = await _summarize_content(query, final_contents)
    
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
          3. 如果是招聘相关，优先补充更容易在公开网页中找到且可抓取的限定词：
              - “官网 招聘 / careers / jobs / join us / hiring”
              - “JD / job description / 任职要求 / 岗位职责 / 内推 / 校招 / 社招”
              尽量避免只指向强反爬的第三方招聘平台（如 Boss/拉勾/猎聘/智联/51job）。
        4. **地域推断**：如果用户使用中文且未明确指定国家（如“美国”、“新加坡”），请默认添加“中国”或“国内”作为限定词，以避免搜索到无关的海外信息。
        5. 保持简短，通常不超过 5 个关键词。
        
        用户问题: {query}
        
        优化后的搜索词 (仅输出一行文本):"""
    )
    chain = prompt | llm | StrOutputParser()
    try:
        return await chain.ainvoke({"query": query})
    except Exception as e:
        print(f"Query Optimization Failed: {e}")
        return query

async def _search_duckduckgo(query: str, limit: int = 3) -> List[dict]:
    """
    私有函数：使用 DuckDuckGo 获取搜索结果 (返回完整对象: href, body, title)
    """
    try:
        # DDGS 是同步库，为了不阻塞异步循环，我们在线程池中运行
        def run_search():
            # 增加超时时间到 10 秒，防止网络波动导致超时
            with DDGS(timeout=10) as ddgs:
                # 策略优化：
                # 1. 增加搜索结果数量 (max_results=8)，然后手动过滤
                # 2. 优先选择包含 "blog", "article", "zhuanlan", "post" 等关键词的 URL
                # 3. 排除掉一些低质量的 SEO 农场或无法访问的站点
                # 4. region="cn-zh" 强制搜索中国地区结果
                results = list(ddgs.text(query, region="cn-zh", max_results=8))
                
                filtered_results = []
                # 优先站点关键词
                priority_domains = [
                    "zhihu.com",
                    "juejin.cn",
                    "csdn.net",
                    "v2ex.com",
                    "segmentfault.com",
                    "cnblogs.com",
                    "infoq.cn",
                    "woshipm.com",
                    # 微信公众号 / 开发者社区
                    "mp.weixin.qq.com",
                    "cloud.tencent.com",
                    "developer.aliyun.com",
                    "huaweicloud.com",
                    "openatom.org",
                    # 开源与问答
                    "github.com",
                    "gitee.com",
                    "stackoverflow.com",
                    # 技术社区/博客
                    "oschina.net",
                    "jianshu.com",
                    "51cto.com",
                    "ruanyifeng.com",
                    "liaoxuefeng.com",
                ]
                # URL 优先关键词（更容易命中“公司官网招聘页/JD镜像/内推帖”等）
                priority_url_keywords = [
                    "/careers",
                    "/career",
                    "/jobs",
                    "/job",
                    "/join",
                    "/join-us",
                    "/hiring",
                    "/recruit",
                    "recruitment",
                    "\u62db\u8058",  # 招聘
                    "\u5185\u63a8",  # 内推
                    "\u6821\u62db",  # 校招
                    "\u793e\u62db",  # 社招
                    "\u4efb\u804c\u8981\u6c42",  # 任职要求
                    "\u5c97\u4f4d\u804c\u8d23",  # 岗位职责
                    "job-description",
                    "job_description",
                    "jd",
                ]
                # 排除站点关键词
                exclude_domains = [
                    "baidu.com",
                    "so.com",
                    "sogou.com",
                    "google.com",
                    "bing.com",
                    "youtube.com",
                    "bilibili.com",
                    # 强反爬招聘站（避免抓取失败浪费额度）
                    "zhipin.com",
                    "lagou.com",
                    "liepin.com",
                    "zhaopin.com",
                    "51job.com",
                    "51job.cn",
                ] # 排除搜索引擎自身/视频站/强反爬招聘站

                # 第一轮：优先筛选高质量社区/博客 或 命中招聘页关键词
                for r in results:
                    url = r['href']
                    url_lc = url.lower()
                    if any(d in url_lc for d in priority_domains) or any(k in url_lc for k in priority_url_keywords):
                        filtered_results.append(r)
                
                # 第二轮：如果不够，补充其他非排除站点的结果
                if len(filtered_results) < limit:
                    for r in results:
                        url = r['href']
                        # Check if already added (by url)
                        if not any(fr['href'] == url for fr in filtered_results) and not any(d in url for d in exclude_domains):
                            filtered_results.append(r)
                            if len(filtered_results) >= limit:
                                break
                
                return filtered_results[:limit]
        
        results = await asyncio.to_thread(run_search)
        print(f"DuckDuckGo 返回结果数: {len(results)}")
        return results
    except Exception as e:
        print(f"DuckDuckGo 搜索异常: {str(e)}")
        return []

async def _crawl_concurrently(urls: List[str]) -> List[str]:
    """
    私有函数：使用 Jina Reader (https://r.jina.ai/) 并发抓取多个 URL
    Jina Reader 是一个免费的云端服务，能将网页直接转换为 Markdown，速度极快。
    """
    contents = []
    
    # 定义单个抓取任务
    async def crawl_one(session, url):
        # 构造 Jina Reader 的 URL
        jina_url = f"https://r.jina.ai/{url}"
        
        try:
            # 性能优化：增加 10 秒超时控制
            async with session.get(jina_url, timeout=10) as response:
                if response.status == 200:
                    text = await response.text()
                    # 简单的去噪：如果返回内容太短，可能是反爬或错误页
                    if len(text) < 100:
                        return ""
                    
                    # 截取前 3000 字符，防止 Token 爆炸
                    return f"来源URL: {url}\n内容摘要:\n{text[:3000]}..."
                else:
                    print(f"Jina Reader 抓取失败 (Status {response.status}): {url}")
                    return ""
        except asyncio.TimeoutError:
            print(f"Jina Reader 抓取超时 (10s): {url}")
            return ""
        except Exception as e:
            print(f"Jina Reader 抓取异常 {url}: {e}")
            return ""

    # 使用 aiohttp 进行并发请求
    async with aiohttp.ClientSession() as session:
        tasks = [crawl_one(session, url) for url in urls]
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
    你的任务是根据用户的问题，从给定的多篇网页抓取内容中，提取**核心信息**。
    
    特别注意：
    - **智能去噪**：用户搜索技术/岗位词（如 "AI Agent"）时，经常会出现无关领域的干扰结果（如“金融代理人”、“前端UI组件”）。请务必**识别并过滤**掉这些明显偏离核心语义的内容，只保留最相关、最硬核的信息。
    - 如果用户询问“岗位需求”或“招聘要求”，请务必提取具体的**硬性技能**（如Python, LangChain）、**软性技能**、**工作职责**、**经验要求**等细节。
    
    要求：
    1. **相关性第一**：如果搜索结果包含多个领域，请优先保留**计算机/人工智能/大模型**领域的内容。
    2. **去除噪音**：忽略广告、导航栏、无关的推荐列表。
    3. **核心优先**：优先保留具体的名词、工具名、技术栈和数据。
    4. **格式清晰**：使用 Markdown 列表整理关键点，**保持简洁**，避免长篇大论。
    5. **不要瞎编**：只能基于提供的【搜索结果】回答。
    6. **统一总结**：请将所有来源的信息**融合**在一起回答，不要按来源分段。
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

async def _perform_bocha_search(query: str) -> str:
    """
    私有函数：调用 Bocha Web Search API
    """
    print(f"--- [Researcher] 开始联网搜索 (Bocha): {query} ---")
    
    url = "https://api.bochaai.com/v1/web-search"
    headers = {
        "Authorization": f"Bearer {settings.BOCHA_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "query": query,
        "freshness": "noLimit", # 不限制时间，获取更多结果
        "summary": True,        # 请求长摘要
        "count": 8              # 获取 8 条结果
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=10) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"Bocha API Error: {response.status} - {error_text}")
                    return f"搜索服务暂时不可用 (Status {response.status})"
                
                data = await response.json()
                
                # 解析 Bocha 返回的数据
                # 兼容两种结构：直接返回 webPages 或 包裹在 data 字段中
                if "data" in data and isinstance(data["data"], dict) and "webPages" in data["data"]:
                    web_pages = data["data"]["webPages"].get("value", [])
                else:
                    web_pages = data.get("webPages", {}).get("value", [])

                if not web_pages:
                    return "未找到相关网络搜索结果。"
                
                # 提取内容
                contents = []
                for page in web_pages:
                    title = page.get("name", "无标题")
                    url = page.get("url", "")
                    # Bocha 的 summary 通常质量很高，优先使用
                    summary = page.get("summary") or page.get("snippet", "")
                    
                    if summary:
                        contents.append(f"来源URL: {url}\n标题: {title}\n内容摘要:\n{summary}")
                
                # 最后还是走一遍 LLM 总结，保证输出格式统一
                print(f"--- [Researcher] Bocha 返回 {len(contents)} 条结果，正在生成最终摘要... ---")
                return await _summarize_content(query, contents)
                
    except Exception as e:
        print(f"Bocha Search Exception: {e}")
        return f"搜索过程中发生错误: {str(e)}"