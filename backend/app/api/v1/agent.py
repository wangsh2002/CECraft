from fastapi import APIRouter, HTTPException
import asyncio
from app.schemas.agent import ChatRequest, AgentResponse, ReviewRequest, ReviewResponse
from app.services.agent_workflow import llm_service
# [新增] 导入我们刚才测试通过的联网搜索工具
from app.services.tools.web_search import perform_web_search
from app.services.tools.rag_retriever import retrieve_resume_examples

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
        # 引入 LangGraph 构建的图
        from app.services.graph_workflow import app_graph
        import uuid
        
        # 构造初始状态
        inputs = {
            "user_input": request.prompt,
            "context_json": request.context,
            "history": request.history,
            "retry_count": 0,
            "is_pass": True,
            "evaluation_feedback": ""
        }
        
        # 生成临时的 thread_id (因为目前 API 是无状态的，每次请求都是新的会话)
        # 如果未来支持长会话，可以从 request header 或 body 中获取 session_id
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        
        # 执行图
        print(f"--- [LangGraph] Start Workflow for: {request.prompt[:20]}... (Thread: {thread_id}) ---")
        final_state = await app_graph.ainvoke(inputs, config=config)
        print("--- [LangGraph] Workflow Finished ---")
        
        final_res = final_state["final_response"]
        
        return AgentResponse(
            intention=final_res["intention"],
            reply=final_res["reply"],
            modified_data=final_res.get("modified_data")
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))