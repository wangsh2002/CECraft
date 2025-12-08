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
        result = await llm_service.process_review_request(request.resume_content)
        
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

# router / api.py

@router.post("/agent", response_model=AgentResponse) 
async def execute_agent_workflow(request: ChatRequest):
    try:
        # === 1. Supervisor 决策 ===
        decision = await llm_service.process_supervisor_request(request.prompt)
        target_agent = decision.get("next_agent") 
        reason = decision.get("reasoning")
        
        print(f"Workflow 决策: {target_agent} | 原因: {reason}")
        
        # === 2. 执行逻辑分流 ===

        # --- 情况 A: 纯调研 (只回答，不改简历) ---
        if target_agent == "research_consult":
            print(f"--- [Research Consult] 启动搜索 ---")
            try:
                search_summary = await perform_web_search(request.prompt)
            except Exception:
                search_summary = "无法获取外部信息"
            
            final_reply = f"{reason}\n\n---\n**为您找到的调研信息：**\n{search_summary}"
            
            return AgentResponse(
                intention="research", # 前端可以用这个标记来决定是否显示"应用修改"按钮
                reply=final_reply,
                modified_data=None # 关键：这里没有 ops 数据
            )

        # --- 情况 B: 调研 + 修改 (链式调用) ---
        elif target_agent == "research_modify":
            print(f"--- [Research & Modify] 启动搜索 + 修改 ---")
            
            # 1. 先搜索
            try:
                # 优化点：对于"根据JD修改"，我们可以把 Prompt 直接作为搜索词，或者让 LLM 提取搜索词
                search_summary = await perform_web_search(request.prompt)
            except Exception:
                search_summary = "（网络搜索失败，将尝试仅根据通用知识修改）"
            
            print(f"--- 搜索完成，传入 Modify Agent ---")

            # 2. 将搜索结果注入 Modify Agent
            # 注意：调用我们在上一步修改过的支持 reference_info 的接口
            agent_result = await llm_service.process_agent_request(
                prompt=request.prompt,        
                context=request.context,      
                reference_info=search_summary 
            )

            # 3. 组装复合回复
            final_reply = (
                f"**参考依据：** 已参考相关职位/行业数据。\n"
                f"{reason}\n"
                f"---\n{agent_result.get('reply')}"
            )

            return AgentResponse(
                intention="modify", 
                reply=final_reply,
                modified_data=agent_result.get("modified_data") # 关键：返回修改数据
            )

        # --- 情况 C: 直接修改 (不搜索) ---
        elif target_agent == "modify":
            print("--- [Direct Modify] ---")
            agent_result = await llm_service.process_agent_request(
                prompt=request.prompt, 
                context=request.context,
                reference_info="无" # 明确告知没有外部参考
            )
            
            return AgentResponse(
                intention="modify",
                reply=agent_result.get("reply"),
                modified_data=agent_result.get("modified_data")
            )

        # --- 情况 D: 闲聊 ---
        else: # chat
            chat_result = await llm_service.process_chat_request(request.prompt)
            return AgentResponse(
                intention="chat",
                reply=chat_result.get("reply"),
                modified_data=None
            )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))