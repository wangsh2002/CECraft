import sys
import os
import asyncio
from datetime import datetime

# 添加 backend 目录到 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from app.services.tools.web_search import perform_web_search
except ImportError:
    # 如果直接在 backend 目录下运行，可能不需要这一步，但为了稳健性保留
    sys.path.append(os.path.join(current_dir, ".."))
    from app.services.tools.web_search import perform_web_search

# 保存目录
SAVE_DIR = os.path.join(current_dir, "data", "resumes_crawled")
os.makedirs(SAVE_DIR, exist_ok=True)

# 定义要搜集的主题列表
# 包含热门技术岗位需求和简历范文
QUERIES = [
    "AI Agent 岗位职责与技能要求",
    "高级Python后端工程师 简历范文",
    "资深前端开发工程师 岗位要求",
    "大模型算法工程师 简历模板",
    "产品经理 核心竞争力与简历撰写",
    "DevOps 工程师 技能图谱与岗位描述",
    "全栈工程师 简历项目经验写法",
    "数据分析师 岗位技能需求"
]

async def crawl_and_save(query):
    print(f"🔍 [Crawl] 正在搜索: {query} ...")
    try:
        # 调用搜索工具
        content = await perform_web_search(query)
        
        # 生成文件名 (替换非法字符)
        safe_name = query.replace(" ", "_").replace("/", "_").replace("\\", "_")
        filename = f"{safe_name}.md"
        filepath = os.path.join(SAVE_DIR, filename)
        
        # 添加元数据头，方便后续 RAG 处理
        file_content = f"""---
query: {query}
date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
source: web_search_tool
---

# {query}

{content}
"""
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(file_content)
            
        print(f"✅ [Saved] 已保存至: {filepath}\n")
        
    except Exception as e:
        print(f"❌ [Error] 搜索 '{query}' 失败: {e}\n")

async def main():
    print(f"🚀 开始批量搜集简历与岗位数据，共 {len(QUERIES)} 个任务")
    print(f"📂 保存路径: {SAVE_DIR}")
    print("-" * 50)
    
    for i, query in enumerate(QUERIES, 1):
        print(f"[{i}/{len(QUERIES)}] 处理任务: {query}")
        await crawl_and_save(query)
        # 稍微停顿一下，避免请求过快
        await asyncio.sleep(2)
        
    print("-" * 50)
    print("🎉 所有搜集任务完成！")

if __name__ == "__main__":
    asyncio.run(main())
