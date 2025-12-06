import sys
import os
import asyncio

# 1. 配置 Python 路径
# 获取当前脚本所在目录 (backend/tests) 的父目录 (backend)，并加入到 sys.path
# 这样才能正确识别 'app' 包 (例如: from app.core.config import settings)
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

try:
    from app.services.tools.web_search import perform_web_search
except ImportError as e:
    print("错误：无法导入 app 模块。请确保你在 backend 目录下运行，或者已正确设置 PYTHONPATH。")
    print(f"详细错误: {e}")
    sys.exit(1)

async def main():
    # 测试用的查询词
    # query = "agent岗位需求" -> "agent" 含义太广，容易搜到房产中介，改为 "AI Agent" 更精准
    query = "AI Agent岗位需求"
    
    print(f"🚀 [Test] 开始测试 perform_web_search，查询词: '{query}'")
    print("-" * 50)

    try:
        # 2. 调用核心搜索函数
        result = await perform_web_search(query)
        
        print("\n✅ [Test] 测试完成，返回结果如下：")
        print("=" * 50)
        print(result)
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ [Test] 测试过程中发生错误: {e}")

if __name__ == "__main__":
    # 3. 运行异步任务
    asyncio.run(main())