import os
import json
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from http import HTTPStatus
import dashscope

# 配置 API Key (实际生产环境建议放入环境变量)
dashscope.api_key = "sk-dd6029b7e0f4419ab4c5bab66d19e30a"

app = FastAPI()

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    prompt: str
    context: str  # 这里接收的是带有 delta 格式的 JSON 字符串

class AgentResponse(BaseModel):
    intention: str  # "modify" | "chat"
    reply: str
    modified_data: Optional[Dict[str, Any]] = None # 修改后的 Delta 数据

def get_agent_prompt(user_prompt: str, context_json: str):
    """
    构建 Agent 的 System Prompt，包含意图识别和 Delta 格式生成的指令。
    """
    return f"""
    你是一个专业的简历优化助手和数据处理 Agent。
    
    ### 任务目标
    1. 分析用户的指令："{user_prompt}"
    2. 分析当前的富文本内容（JSON格式）：{context_json}
    3. 判断用户意图是 "修改内容" (modify) 还是 "普通闲聊/提问" (chat)。
    4. 如果是 "modify"，你需要根据用户指令修改内容，并严格按照原有的 JSON 结构（Quill/Delta 格式）返回修改后的数据。

    ### Delta 格式说明
    Delta 格式通常包含 "ops" 数组，每个元素包含 "insert" (文本) 和可选的 "attributes" (样式)。
    例如：{{"ops": [{{"insert": "Hello"}}, {{"insert": "World", "attributes": {{"bold": true}}}}]}}
    **必须保持原有的数据结构层级，只修改 insert 的文本内容或对应的 attributes。**

    ### 输出格式（必须是严格的 JSON）
    请只输出一个 JSON 对象，不要包含 markdown 标记或额外解释。格式如下：
    {{
        "intention": "modify" 或 "chat",
        "reply": "给用户的简短回复，解释你做了什么或回答问题",
        "modified_data": {{ ...这里是修改后的完整 Delta JSON 对象，如果是 chat 则为 null... }}
    }}
    """

@app.post("/api/ai/agent")
async def ai_agent_process(request: ChatRequest):
    try:
        # 1. 构建 Prompt
        system_prompt = get_agent_prompt(request.prompt, request.context)
        
        # 2. 调用通义千问 (qwen-flash)
        response = dashscope.Generation.call(
            model="qwen-flash",
            messages=[
                {'role': 'system', 'content': '你是一个严格遵循 JSON 输出格式的智能助手。'},
                {'role': 'user', 'content': system_prompt}
            ],
            result_format='message',  # 设置输出为 message 格式
        )

        if response.status_code == HTTPStatus.OK:
            content = response.output.choices[0].message.content
            print("AI Response Raw:", content)
            
            # 3. 解析 AI 返回的 JSON
            try:
                # 尝试清洗 markdown 标记 (如果是 ```json 包裹的)
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.strip("`")
                
                result_json = json.loads(content)
                
                return AgentResponse(
                    intention=result_json.get("intention", "chat"),
                    reply=result_json.get("reply", "处理完成"),
                    modified_data=result_json.get("modified_data")
                )
            except json.JSONDecodeError:
                # 如果 AI 没返回 JSON，兜底为普通对话
                return AgentResponse(
                    intention="chat",
                    reply=content, # 直接返回原始内容作为回复
                    modified_data=None
                )
        else:
            raise HTTPException(status_code=500, detail=f"AI Service Error: {response.message}")

    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)