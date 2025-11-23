import os
import uvicorn
import json
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

# --- Pydantic Models ---
class ChatRequest(BaseModel):
    prompt: str
    context: str

class AgentResponse(BaseModel):
    intention: str
    reply: str
    modified_data: Optional[Dict[str, Any]] = None

# --- LangChain Setup ---

# 1. 初始化模型
llm = ChatTongyi(
    model="qwen-flash",
    dashscope_api_key=DASHSCOPE_API_KEY,
    temperature=0.1,  # 低温度有助于严格遵守格式指令
)

# 2. 定义系统提示词模板 (包含新的约束条件)
system_prompt_text = """
你是一个专业的简历优化助手和数据处理 Agent。

### 任务目标
1. 分析用户的指令。
2. 参考提供的上下文内容（可能是 Sketch 内部格式）。
3. 判断用户意图是 "修改内容" (modify) 还是 "普通闲聊/提问" (chat)。
4. 如果是 "modify"，请根据用户指令修改内容，并**必须将其转换为标准的 Quill Delta 格式**输出。

### ⚠️ 内容保持与格式约束 (重要)
1. **结构保持**：请尽量**保持原有的段落数量、换行结构和列表项数量**。除非用户明确要求大幅重组或扩充，否则请只在原有框架下进行润色，不要随意合并或拆分段落。
2. **空格保留**：文本中的空格（尤其是连续的空格）通常用于对齐或特殊排版，请**务必原样保留**，不要将其压缩、合并或删除。
   - 例如："技能     Java" 中的多个空格应保留。
3. **英文规范**：虽然要保留对齐空格，但**严禁**在英文单词内部插入错误的空格（例如不要将 "Project" 变成 "P r o j e c t"）。

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
    "reply": "已为您优化工作经历部分的描述，使其更加专业，并保持了原有的排版格式。",
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

# 4. 初始化输出解析器
parser = JsonOutputParser()

# 5. 构建 Chain
chain = prompt_template | llm | parser

@app.post("/api/ai/agent")
async def ai_agent_process(request: ChatRequest):
    try:
        # 调试：输出前端发送的完整请求内容（以 JSON 格式美观打印）
        try:
            body_json = json.dumps(request.dict(), ensure_ascii=False, indent=2)
        except Exception:
            body_json = str(request)
        print("Received request body:", body_json)
        
        # 调用 Chain
        result = chain.invoke({
            "user_prompt": request.prompt,
            "context_json": request.context
        })
        
        print("AI Response:", result)
        
        # 构造响应并调试输出（打印发送给前端的内容）
        response_obj = AgentResponse(
            intention=result.get("intention", "chat"),
            reply=result.get("reply", "处理完成"),
            modified_data=result.get("modified_data")
        )

        try:
            resp_json = json.dumps(response_obj.dict(), ensure_ascii=False, indent=2)
        except Exception:
            resp_json = str(response_obj)
        print("Sending response body:", resp_json)

        return response_obj

    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)