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
    print("错误：无法导入 app 模块。请确保你在 backend 目录下运行，或者已正确设置 PYTHONPATH。")
    print(f"详细错误: {e}")
    sys.exit(1)

async def run_test_case(name: str, prompt: str, context: dict = None, expected_final_intent: str = None):
    print(f"\n🚀 [Test Case] {name}")
    print(f"📝 Input: {prompt}")
    
    if context is None:
        context = {}
    
    # 构造初始状态
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
        # 执行图
        final_state = await app_graph.ainvoke(inputs, config=config)
        final_res = final_state["final_response"]
        
        actual_intent = final_res["intention"]
        reply = final_res["reply"]
        modified_data = final_res.get("modified_data")
        reference_info = final_state.get("reference_info", "")
        
        print("-" * 30)
        print(f"🎯 Actual Intent: {actual_intent}")
        print(f"💬 Reply Preview: {reply[:100]}..." if reply else "💬 Reply: (Empty)")
        
        if reference_info and reference_info != "无":
             print(f"📚 Reference Info Length: {len(reference_info)} chars")
        
        if modified_data:
            print(f"✨ Modified Data: Present (Keys: {list(modified_data.keys())})")
        
        # 验证逻辑
        success = True
        if expected_final_intent and actual_intent != expected_final_intent:
            print(f"❌ Intent Mismatch: Expected {expected_final_intent}, got {actual_intent}")
            success = False
            
        # 特殊验证：如果是调研类，检查是否有参考信息
        if "调研" in name and (not reference_info or reference_info == "无"):
            print("⚠️ Warning: Expected reference info but got none.")
            # 搜索可能失败，但不一定代表流程错误，所以只警告
            
        if success:
            print("✅ Test Passed")
        else:
            print("❌ Test Failed")
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()

async def main():
    print("========================================")
    print("🧪 Starting Backend Intent Integration Tests")
    print("========================================")

    # Case 1: Chat (闲聊)
    await run_test_case(
        name="Intent: Chat",
        prompt="你好，请介绍一下你自己。",
        expected_final_intent="chat"
    )

    # Case 2: Research Consult (纯调研)
    # 注意：research_consult 在 graph 中最终会流转到 chat 节点，所以 final intent 是 chat
    # 但我们会检查是否有 reference_info
    await run_test_case(
        name="Intent: Research Consult (Should route to Chat with Info)",
        prompt="帮我查一下2024年Python后端工程师的平均薪资。",
        expected_final_intent="chat"
    )

    # Case 3: Modify (直接修改)
    await run_test_case(
        name="Intent: Modify (Direct)",
        prompt="把这段经历改得更专业一点，用STAR法则。",
        context={"ops": [{"insert": "我负责写代码，修复bug，维护服务器。"}]},
        expected_final_intent="modify"
    )

    # Case 4: Research Modify (调研 + 修改)
    await run_test_case(
        name="Intent: Research Modify",
        prompt="根据现在大厂对AI Agent的要求，优化我的技能描述。",
        context={"ops": [{"insert": "熟悉 Python, LangChain, LLM 开发。"}]},
        expected_final_intent="modify"
    )

if __name__ == "__main__":
    asyncio.run(main())
