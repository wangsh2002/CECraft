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
    2. 参考提供的上下文内容（可能是 Sketch 内部格式）：{context_json}
    3. 判断用户意图是 "修改内容" (modify) 还是 "普通闲聊/提问" (chat)。
    4. 如果是 "modify"，请根据用户指令修改内容，并**必须将其转换为标准的 Quill Delta 格式**输出。

    ### Delta 格式严格要求
    修改后的数据 (modified_data) 必须是一个包含 "ops" 数组的对象。
    **关键：请务必将原始属性转换为标准的 Quill/BlockKit 属性，不要保留原始的业务字段（如 WEIGHT, SIZE 等）。**
    
    请遵循以下属性映射规则：
    - 加粗：使用 {{"bold": true}} (替代 WEIGHT: "bold")
    - 字号：使用 {{"fontSize": 14}} (替代 SIZE)
    - 颜色：使用 {{"color": "#333333"}}
    - 背景：使用 {{"background": "#eeeeee"}}
    - 列表：使用 {{"list": "bullet"}} 或 {{"list": "ordered"}} (替代 UNORDERED_LIST_LEVEL)
      * 注意：列表属性必须附加在换行符 "\\n" 上。
    - 链接：使用 {{"link": "url"}}
    
    ### 输出示例
    {{
        "intention": "modify",
        "reply": "已为您优化工作经历部分的描述，使其更加专业。",
        "modified_data": {{
            "ops": [
                {{ "insert": "工作经历", "attributes": {{ "bold": true, "fontSize": 18 }} }},
                {{ "insert": "\\n", "attributes": {{ "header": 2 }} }},
                {{ "insert": "负责前端性能优化，提升加载速度 30%。" }},
                {{ "insert": "\\n", "attributes": {{ "list": "bullet" }} }}
            ]
        }}
    }}

    ### 你的输出
    请只输出一个合法的 JSON 对象，不要包含 Markdown 标记（如 ```json）。
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
                {'role': 'system', 'content': '你是一个严格遵循 JSON 输出格式的智能助手，负责处理富文本数据转换。'},
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