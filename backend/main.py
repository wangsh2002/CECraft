# main.py

import uvicorn
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

# [关键步骤] 从新文件引入做好的 Chain
from agent_management import agent_chain, review_chain

app = FastAPI()

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 数据模型 (Pydantic Models)
# ==========================================
# (这些留在这里没问题，也可以再新建一个 schemas.py 放进去，看你喜好)

class ChatRequest(BaseModel):
    prompt: str
    context: str

class AgentResponse(BaseModel):
    intention: str
    reply: str
    modified_data: Optional[Dict[str, Any]] = None

class ReviewRequest(BaseModel):
    resume_content: str

class ReviewResponse(BaseModel):
    score: int
    summary: str
    pros: List[str]
    cons: List[str]
    suggestions: List[str]

# ==========================================
# API 路由
# ==========================================

# 1. 诊断接口
@app.post("/api/ai/review")
async def ai_review_process(request: ReviewRequest):
    try:
        print(f"收到诊断请求，内容长度: {len(request.resume_content)}")
        
        # 直接调用从 agent_management 导入的 chain
        result = review_chain.invoke({
            "resume_content": request.resume_content
        })
        
        print("诊断完成:", result)
        
        response_obj = ReviewResponse(
            score=result.get("score", 0),
            summary=result.get("summary", "无法生成点评"),
            pros=result.get("pros", []),
            cons=result.get("cons", []),
            suggestions=result.get("suggestions", [])
        )
        return response_obj

    except Exception as e:
        print(f"Review Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 2. 修改接口
@app.post("/api/ai/agent")
async def ai_agent_process(request: ChatRequest):
    try:
        print(f"收到修改请求: {request.prompt}")
        
        # 直接调用从 agent_management 导入的 chain
        result = agent_chain.invoke({
            "user_prompt": request.prompt,
            "context_json": request.context
        })
        
        response_obj = AgentResponse(
            intention=result.get("intention", "chat"),
            reply=result.get("reply", "处理完成"),
            modified_data=result.get("modified_data")
        )
        return response_obj

    except Exception as e:
        print(f"Agent Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)