import sys
import os
import asyncio
import json
import uuid
import re

# 1. 配置 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

try:
    from app.services.graph_workflow import app_graph
except ImportError as e:
    print("错误：无法导入 app 模块。")
    sys.exit(1)

def contains_emoji(text):
    if not text:
        return False
    # 简单的 emoji 匹配范围
    emoji_pattern = re.compile("[\U00010000-\U0010ffff]", flags=re.UNICODE)
    return emoji_pattern.search(text) is not None

async def main():
    print("========================================")
    print("🧪 Testing No Emoji Constraint")
    print("========================================")

    prompt = "帮我把这段经历改得更专业一点：我在公司负责写代码，用过python和java，做过一个商城项目。"
    context = {
        "resume": {
            "work_experience": [
                {
                    "company": "Test Co",
                    "description": "我在公司负责写代码，用过python和java，做过一个商城项目。"
                }
            ]
        }
    }

    inputs = {
        "user_input": prompt,
        "context_json": json.dumps(context, ensure_ascii=False),
        "history": [],
        "retry_count": 0,
        "is_pass": True,
        "evaluation_feedback": ""
    }
    
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        final_state = await app_graph.ainvoke(inputs, config=config)
        final_res = final_state["final_response"]
        
        # 注意：final_response 的结构可能因 agent 而异，通常 agent 会返回 modified_content
        # 如果是 modify 意图，通常会有 modified_content
        
        modified_content = final_res.get("modified_content", "")
        reply = final_res.get("reply", "")
        
        print(f"Modified Content: {modified_content}")
        print(f"Reply: {reply}")
        
        if contains_emoji(modified_content):
            print("❌ Test Failed: Modified content contains emoji.")
        else:
            print("✅ Test Passed: Modified content does not contain emoji.")
            
        if contains_emoji(reply):
             print("⚠️ Warning: Reply contains emoji (this might be acceptable but check context).")

    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
