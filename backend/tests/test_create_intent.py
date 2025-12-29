import sys
import os
import asyncio
import json
import uuid

# 1. 配置 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

try:
    from app.services.graph_workflow import app_graph
except ImportError as e:
    print("错误：无法导入 app 模块。")
    sys.exit(1)

async def main():
    print("========================================")
    print("🧪 Testing Create Intent")
    print("========================================")

    # Case 1: Create without research
    prompt = "帮我写一段简短的自我介绍，强调我有3年Python经验。"
    # Empty context for create
    context = {} 
    block_size = {"width": 500, "height": 100} # Constraint

    inputs = {
        "user_input": prompt,
        "context_json": json.dumps(context, ensure_ascii=False),
        "history": [],
        "retry_count": 0,
        "is_pass": True,
        "evaluation_feedback": "",
        "block_size": block_size
    }
    
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        print(f"📝 Input: {prompt}")
        final_state = await app_graph.ainvoke(inputs, config=config)
        final_res = final_state["final_response"]
        
        actual_intent = final_res["intention"]
        reply = final_res.get("reply", "")
        modified_data = final_res.get("modified_data")
        
        print("-" * 30)
        print(f"🎯 Actual Intent: {actual_intent}")
        print(f"💬 Reply: {reply}")
        
        if modified_data:
            print(f"✨ Modified Data: {json.dumps(modified_data, ensure_ascii=False)}")
        else:
            print("❌ Modified Data: Missing")

        if actual_intent in ["create", "research_create"]:
            print("✅ Intent is correct (create/research_create)")
        else:
            print(f"❌ Intent mismatch: Expected create/research_create, got {actual_intent}")

    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
