from fastapi import APIRouter, HTTPException
from app.schemas.agent import ChatRequest, AgentResponse, ReviewRequest, ReviewResponse
from app.services.agent_workflow import llm_service

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

@router.post("/agent", response_model=AgentResponse) 
async def execute_agent_workflow(request: ChatRequest):
    """
    [智能体工作流入口]
    接收用户指令 -> 大脑路由 -> 执行任务 -> 返回统一格式 AgentResponse
    """
    try:
        # === 1. 大脑思考 (Supervisor) ===
        decision = await llm_service.process_supervisor_request(request.prompt)
        
        target_agent = decision.get("next_agent") 
        reason = decision.get("reasoning")
        
        # === 2. 执行具体 Agent 逻辑并组装响应 ===
        
        # --- 情况 A: 调研专员 (Researcher) ---
        if target_agent == "research":
            # 模拟调用调研逻辑 (未来替换为真实函数)
            # content = await llm_service.process_research(request.message)
            content = f"收到，正在根据您的要求调研相关 JD 和背景信息... (基于意图: {reason})"
            
            return AgentResponse(
                intention="research",
                reply=content,
                modified_data=None # 调研不需要改简历数据
            )

        # --- 情况 B: 修改 (modify) ---
        elif target_agent == "modify":
            # 调用 Modify Agent 获取修改结果
            # 假设 process_agent_request 返回的是 {"intention": "modify", "reply": "...", "modified_data": ...}
            # 如果你的 LLMService 直接返回对象，这里可能需要适配一下
            
            agent_result = llm_service.process_agent_request(
                prompt=request.prompt, 
                context=request.context # 这里需填入当前的简历上下文
            )
            
            # 确保即使 Agent 返回格式有细微差别，也能兜底
            return AgentResponse(
                intention="modify",
                reply=agent_result.get("reply", "处理完成"),
                modified_data=agent_result.get("modified_data") # 这里包含 ops
            )
        # --- 情况 C: 闲聊/其他 (Chat) ---
        elif target_agent == "chat":

            return AgentResponse(
                intention="chat",
                reply=f"好的。({reason})", # 简单回复，或者调用 chat_chain
                modified_data=None
            )

    except Exception as e:
        print(f"Workflow Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))