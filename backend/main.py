import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any

# LangChain 相关引入
from langchain_community.chat_models import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# 配置 API Key
DASHSCOPE_API_KEY = "sk-dd6029b7e0f4419ab4c5bab66d19e30a"

app = FastAPI()

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models (保持接口一致) ---
class ChatRequest(BaseModel):
    prompt: str
    context: str  # 接收 JSON 字符串上下文

class AgentResponse(BaseModel):
    intention: str  # "modify" | "chat"
    reply: str
    modified_data: Optional[Dict[str, Any]] = None

# --- LangChain Setup ---

# 1. 初始化模型 (Qwen)
llm = ChatTongyi(
    model="qwen-flash",
    dashscope_api_key=DASHSCOPE_API_KEY,
    temperature=0.1,  # 降低随机性，保证 JSON 格式稳定
)

# 2. 定义系统提示词模板
# 注意：JSON 样例中的大括号需要用双大括号 {{ }} 转义
system_prompt_text = """
你是一个专业的简历优化助手和数据处理 Agent。

### 任务目标
1. 分析用户的指令
2. 参考提供的上下文内容（可能是 Sketch 内部格式）
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
  * ⚠️ 注意：列表属性**仅**需附加在换行符 "\\n" 上，**切勿**附加在文本内容上。
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

# 3. 构建 Prompt Template
prompt_template = ChatPromptTemplate.from_messages([
    ("system", system_prompt_text),
    ("user", "用户的指令：{user_prompt}\n上下文内容：{context_json}")
])

# 4. 初始化输出解析器 (自动清洗 Markdown 代码块并转为 Dict)
parser = JsonOutputParser()

# 5. 构建 Chain (LCEL 语法)
chain = prompt_template | llm | parser

@app.post("/api/ai/agent")
async def ai_agent_process(request: ChatRequest):
    try:
        print(f"Received Prompt: {request.prompt}")
        
        # 调用 Chain
        result = chain.invoke({
            "user_prompt": request.prompt,
            "context_json": request.context
        })
        
        print("AI Response:", result)
        
        # 构造响应
        return AgentResponse(
            intention=result.get("intention", "chat"),
            reply=result.get("reply", "处理完成"),
            modified_data=result.get("modified_data")
        )

    except Exception as e:
        print(f"Error: {str(e)}")
        # 发生错误时返回 500
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)