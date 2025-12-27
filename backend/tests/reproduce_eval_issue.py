
import asyncio
import json
import os
import sys
from dotenv import load_dotenv

# Add backend to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.agent_workflow import llm_service

# Mock Context (Quill Delta format)
MOCK_CONTEXT = json.dumps({
    "ops": [
        {"insert": "熟悉HTML5,CSS3,ES6，了解常用网络协议、数据结构，熟悉Chromium架构\n"},
        {"insert": "熟练使用Vue2、Vue3全家桶开发，能使用React开发，对Vue源码以及架构有较深的理解\n"}
    ]
})

async def reproduce_eval():
    load_dotenv()
    print("--- Starting Evaluation Reproduction ---")
    
    user_prompt = "把技能关键词加粗"
    
    # Mock Agent Reply (Correctly formatted)
    agent_reply = "已为您将技能关键词加粗。"
    modified_data = {
        "ops": [
            {"insert": "熟悉", "attributes": {"bold": True}},
            {"insert": "HTML5,"},
            {"insert": "CSS3", "attributes": {"bold": True}},
            {"insert": ",ES6\n"}
        ]
    }
    
    print(f"User Prompt: {user_prompt}")
    print(f"Agent Reply: {agent_reply}")
    print(f"Modified Data Snippet: {str(modified_data)[:100]}...")
    
    try:
        result = await llm_service.process_evaluation_request(
            user_prompt=user_prompt,
            agent_reply=agent_reply,
            reference_info="无",
            modified_data=modified_data
        )
        
        print("\n--- Evaluation Result ---")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        if result.get("is_pass"):
            print("\n✅ PASS: Evaluation passed.")
        else:
            print("\n❌ FAIL: Evaluation failed.")

    except Exception as e:
        print(f"\n❌ Exception: {e}")

if __name__ == "__main__":
    asyncio.run(reproduce_eval())
