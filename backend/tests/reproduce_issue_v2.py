
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
        {"insert": "大数据专业 本科 计算机科学与技术学院 \n"},
        {"insert": "—阿里巴巴-蚂蚁集团 开源团队 AntV、Umi 团队成员、Ant Design Collaborator\n"},
        {"insert": "—若干知名开源项目代码贡献:蚂蚁 AntDesign、Umi、G2、S2、G6VP 等、腾讯 Omi Design、阿里 ahooks、Element Plus、字 节 byted-hook、web doctor等\n"},
        {"insert": "---2022腾讯犀牛鸟开源人才计划--OMI贡献排行 第三(证书)\n"}
    ]
})

async def reproduce():
    load_dotenv()
    print("--- Starting Reproduction ---")
    
    user_prompt = "润色一下"
    
    print(f"User Prompt: {user_prompt}")
    print(f"Context: {MOCK_CONTEXT}")
    
    try:
        result = await llm_service.process_agent_request(
            prompt=user_prompt,
            context=MOCK_CONTEXT,
            reference_info="无",
            history=[]
        )
        
        print("\n--- Result ---")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        if result.get("modified_data"):
            ops = result["modified_data"].get("ops", [])
            full_text = "".join([op.get("insert", "") for op in ops])
            print("\n--- Modified Text ---")
            print(full_text)
            
            if "字 节" in full_text:
                print("\n❌ FAIL: '字 节' space not fixed.")
            else:
                print("\n✅ PASS: '字 节' space fixed.")
                
            if "；" in full_text:
                 print("✅ PASS: Semicolon used.")
            else:
                 print("⚠️ WARNING: Semicolon not used (might be okay if structure changed).")
                 
            # Check for list attributes
            has_list = any(op.get("attributes", {}).get("list") for op in ops)
            if has_list:
                print("✅ PASS: List attributes used.")
            else:
                print("❌ FAIL: List attributes NOT used.")

        else:
            print("\n❌ FAIL: No modified_data returned.")

    except Exception as e:
        print(f"\n❌ Exception: {e}")

if __name__ == "__main__":
    asyncio.run(reproduce())
