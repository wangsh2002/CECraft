from fastapi import APIRouter, HTTPException
from app.schemas.agent import ChatRequest, AgentResponse, ReviewRequest, ReviewResponse
from app.services.llm_service import llm_service

router = APIRouter()

# 1. 诊断接口
@router.post("/review", response_model=ReviewResponse)
async def ai_review_process(request: ReviewRequest):
    try:
        print(f"收到诊断请求，内容长度: {len(request.resume_content)}")
        
        # 调用 Service
        result = llm_service.process_review_request(request.resume_content)
        
        print("诊断完成:", result)
        
        return ReviewResponse(
            score=result.get("score", 0),
            summary=result.get("summary", "无法生成点评"),
            pros=result.get("pros", []),
            cons=result.get("cons", []),
            suggestions=result.get("suggestions", [])
        )

    except Exception as e:
        print(f"Review Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 2. 修改接口
@router.post("/agent", response_model=AgentResponse)
async def ai_agent_process(request: ChatRequest):
    try:
        print(f"收到修改请求: {request.prompt}")
        
        # 调用 Service
        result = llm_service.process_agent_request(request.prompt, request.context)
        
        return AgentResponse(
            intention=result.get("intention", "chat"),
            reply=result.get("reply", "处理完成"),
            modified_data=result.get("modified_data")
        )

    except Exception as e:
        print(f"Agent Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))