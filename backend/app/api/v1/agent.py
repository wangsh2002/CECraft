from fastapi import APIRouter, HTTPException
from app.schemas.agent import ChatRequest, AgentResponse, ReviewRequest, ReviewResponse
from app.services.agent_workflow import llm_service
# [新增] 导入我们刚才测试通过的联网搜索工具
from app.services.tools.web_search import perform_web_search

router = APIRouter()

# 1. 诊断接口
@router.post("/review", response_model=ReviewResponse)
async def ai_review_process(request: ReviewRequest):
    try:
        print(f"收到诊断请求，内容长度: {len(request.resume_content)}")
        
        # 调用 Service
        # 注意：如果 process_review_request 是异步函数，记得加 await
        # 这里保持你原有的同步调用写法，如果报错 'coroutine object'，请改为 await llm_service...
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
        # 这里的 prompt 比如是："帮我查一下现在 Java 高级开发的 JD 要求"
        decision = await llm_service.process_supervisor_request(request.prompt)
        
        target_agent = decision.get("next_agent") 
        reason = decision.get("reasoning")
        
        print(f"Workflow 决策: 目标Agent={target_agent}, 理由={reason}")
        
        # === 2. 执行具体 Agent 逻辑并组装响应 ===
        
        # --- 情况 A: 调研专员 (Researcher) ---
        if target_agent == "research":
            print(f"--- [Researcher] 启动联网搜索: {request.prompt} ---")
            
            # [核心修改] 真实调用 Web Search
            # perform_web_search 是异步函数，必须加 await
            try:
                search_summary = await perform_web_search(request.prompt)
            except Exception as e:
                print(f"搜索工具执行失败: {e}")
                search_summary = "抱歉，联网搜索服务暂时不可用。"

            # 组装更友好的回复
            final_reply = f"{reason}\n\n---\n**为您找到的调研信息：**\n{search_summary}"

            return AgentResponse(
                intention="research",
                reply=final_reply,
                modified_data=None # 调研通常只返回文本，不修改简历
            )

        # --- 情况 B: 修改 (modify) ---
        elif target_agent == "modify":
            print("--- [Modify] 进入修改模式 ---")
            # 调用 Modify Agent 获取修改结果
            # 如果 process_agent_request 内部涉及 LLM 调用，建议查看是否需要 await
            agent_result = llm_service.process_agent_request(
                prompt=request.prompt, 
                context=request.context # 简历上下文
            )
            
            return AgentResponse(
                intention="modify",
                reply=agent_result.get("reply", "处理完成"),
                modified_data=agent_result.get("modified_data") # 这里包含 ops
            )

        # --- 情况 C: 闲聊/其他 (Chat) ---
        elif target_agent == "chat":
            print("--- [Chat] 进入闲聊模式 ---")
            chat_result = llm_service.process_chat_request(prompt=request.prompt)

            return AgentResponse(
                intention="chat",
                reply=chat_result.get("reply", f"好的，收到。({reason})"), 
                modified_data=None
            )

        # --- 兜底 ---
        else:
             return AgentResponse(
                intention="chat",
                reply=f"收到指令，但暂不支持该操作 ({target_agent})。",
                modified_data=None
            )

    except Exception as e:
        print(f"Workflow Error: {str(e)}")
        # 打印详细堆栈有助于调试
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))