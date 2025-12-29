from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
import asyncio
import json
from app.schemas.agent import ChatRequest, AgentResponse, ReviewRequest, ReviewResponse
from app.services.agent_workflow import llm_service
# [新增] 导入我们刚才测试通过的联网搜索工具
from app.services.tools.web_search import perform_web_search
from app.services.tools.rag_retriever import retrieve_resume_examples
from app.api import deps
from app.models.user import User

router = APIRouter()

# 1. 诊断接口
@router.post("/review", response_model=ReviewResponse)
async def ai_review_process(
    request: ReviewRequest,
    current_user: User = Depends(deps.get_current_user)
):
    try:
        print(f"收到诊断请求，内容长度: {len(request.resume_content)}")
        print(f"用户: {current_user.email}")
        
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

@router.post("/agent") 
async def execute_agent_workflow(
    request: ChatRequest,
    current_user: User = Depends(deps.get_current_user)
):
    try:
        # 引入 LangGraph 构建的图
        from app.services.graph_workflow import app_graph
        import uuid
        
        print(f"用户: {current_user.email} 请求 Agent")

        # 构造初始状态
        inputs = {
            "user_input": request.prompt,
            "context_json": request.context,
            "history": request.history,
            "retry_count": 0,
            "is_pass": True,
            "evaluation_feedback": "",
            "block_size": request.block_size
        }
        
        # 生成临时的 thread_id
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        
        print(f"--- [LangGraph] Start Workflow for: {request.prompt[:20]}... (Thread: {thread_id}) ---")

        async def event_generator():
            try:
                # 1. 初始状态
                yield json.dumps({"type": "status", "content": "正在分析您的意图..."}) + "\n"
                
                # 2. 监听图执行事件
                async for event in app_graph.astream(inputs, config=config):
                    for node_name, state_update in event.items():
                        # 根据当前完成的节点，预测下一个状态并发送反馈
                        if node_name == "supervisor":
                            next_step = state_update.get("next_step")
                            if next_step in ["research_consult", "research_modify", "research_create"]:
                                yield json.dumps({"type": "status", "content": "正在进行深度调研 (联网/RAG)..."}) + "\n"
                            elif next_step in ["modify", "create"]:
                                yield json.dumps({"type": "status", "content": "正在撰写/修改简历..."}) + "\n"
                            else:
                                yield json.dumps({"type": "status", "content": "正在思考回复..."}) + "\n"
                        
                        elif node_name == "research":
                            yield json.dumps({"type": "status", "content": "调研完成，正在整理信息..."}) + "\n"

                        elif node_name == "modify":
                            yield json.dumps({"type": "status", "content": "正在评估修改质量..."}) + "\n"

                        elif node_name == "evaluation":
                            if state_update.get("is_pass"):
                                yield json.dumps({"type": "status", "content": "评估通过，正在生成最终回复..."}) + "\n"
                            else:
                                yield json.dumps({"type": "status", "content": "评估未通过，正在重新优化..."}) + "\n"

                        # 3. 检查是否有最终结果
                        if "final_response" in state_update:
                            final_res = state_update["final_response"]
                            response_data = {
                                "intention": final_res.get("intention", "chat"),
                                "reply": final_res.get("reply", ""),
                                "modified_data": final_res.get("modified_data")
                            }
                            yield json.dumps({"type": "result", "data": response_data}) + "\n"
            except Exception as e:
                print(f"Stream Error: {e}")
                yield json.dumps({"type": "status", "content": f"处理过程中发生错误: {str(e)}"}) + "\n"
                # 返回一个错误的最终结果，避免前端无限等待
                error_data = {
                    "intention": "chat",
                    "reply": f"抱歉，系统处理您的请求时遇到问题: {str(e)}",
                    "modified_data": None
                }
                yield json.dumps({"type": "result", "data": error_data}) + "\n"

        return StreamingResponse(event_generator(), media_type="application/x-ndjson")

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))