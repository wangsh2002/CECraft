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
        # === 1. Supervisor 决策 ===
        decision = await llm_service.process_supervisor_request(request.prompt, request.history)
        target_agent = decision.get("next_agent") 
        print(f"Workflow 决策: {target_agent}")

        # === 初始化公共变量 ===
        final_intention = "chat"
        final_reply_text = ""
        final_modified_data = None
        
        # 专门用于存储上下文信息的变量，后续会传给评估者和重试逻辑
        # 默认包含 Context，如果进行了搜索，会追加搜索结果
        current_reference_info = "无外部参考信息" 

        # === 2. 初次执行 (First Pass) ===
        
        # [A] 纯调研
        if target_agent == "research_consult":
            final_intention = "research"
            
            # 并行执行 Web 搜索和 RAG 检索
            web_task = asyncio.create_task(perform_web_search(request.prompt))
            rag_task = asyncio.to_thread(retrieve_resume_examples, request.prompt)
            
            web_res, rag_res = await asyncio.gather(web_task, rag_task, return_exceptions=True)
            
            # 处理可能的异常
            if isinstance(web_res, Exception):
                web_res = f"Web Search Error: {str(web_res)}"
            if isinstance(rag_res, Exception):
                rag_res = f"RAG Search Error: {str(rag_res)}"

            combined_res = f"**Web Search Result:**\n{web_res}\n\n**RAG Search Result:**\n{rag_res}"
            current_reference_info = combined_res
            final_reply_text = f"**调研结果：**\n{combined_res}"
            # 注意：纯调研通常不涉及 modified_data，但在重试时我们可能希望 LLM 介入润色
            
        # [B] 调研 + 修改
        elif target_agent == "research_modify":
            final_intention = "modify"
            
            # 并行执行 Web 搜索和 RAG 检索
            web_task = asyncio.create_task(perform_web_search(request.prompt))
            rag_task = asyncio.to_thread(retrieve_resume_examples, request.prompt)
            
            web_res, rag_res = await asyncio.gather(web_task, rag_task, return_exceptions=True)
            
            # 处理可能的异常
            if isinstance(web_res, Exception):
                web_res = f"Web Search Error: {str(web_res)}"
            if isinstance(rag_res, Exception):
                rag_res = f"RAG Search Error: {str(rag_res)}"

            combined_res = f"**Web Search Result:**\n{web_res}\n\n**RAG Search Result:**\n{rag_res}"
            current_reference_info = combined_res # 搜索结果作为参考
            
            agent_result = await llm_service.process_agent_request(
                prompt=request.prompt,
                context=request.context,
                reference_info=current_reference_info,
                history=request.history
            )
            final_reply_text = agent_result.get("reply")
            final_modified_data = agent_result.get("modified_data")

        # [C] 直接修改
        elif target_agent == "modify":
            final_intention = "modify"
            current_reference_info = "无"
            
            agent_result = await llm_service.process_agent_request(
                prompt=request.prompt,
                context=request.context,
                reference_info=current_reference_info,
                history=request.history
            )
            final_reply_text = agent_result.get("reply")
            final_modified_data = agent_result.get("modified_data")

        # [D] 闲聊 (通常不需要评估)
        else:
            chat_res = await llm_service.process_chat_request(request.prompt, request.history)
            return AgentResponse(intention="chat", reply=chat_res.get("reply"))

        # === 3. 质量评估 (Evaluation) ===
        print("--- [Evaluation] 开始质检 ---")
        eval_result = await llm_service.process_evaluation_request(
            user_prompt=request.prompt,
            agent_reply=final_reply_text,
            reference_info=current_reference_info
        )
        
        is_pass = eval_result.get("is_pass", True)
        print(f"初次评估结果: {'✅ 通过' if is_pass else '❌ 未通过'} | 分数: {eval_result.get('score')}")

        # === 4. 自愈重试 (Self-Correction Loop) ===
        # 条件：评估未通过 且 意图是修改类 (modify/research_modify)
        # (如果是 research_consult 纯搜索失败，通常是因为搜不到，LLM 重写也救不了，所以跳过)
        if not is_pass and final_intention == "modify":
            
            print("--- [Retry] 触发自动修正逻辑 ---")
            
            # (1) 提取“专家意见”
            suggestions = eval_result.get("suggestion", "请检查用户需求是否满足")
            missing_points = ", ".join(eval_result.get("missing_points", []))
            
            # (2) 构造“加强版”参考信息
            # 将原始参考信息 + 修正指令合并
            retry_reference_info = f"""
            {current_reference_info}
            
            =========================================
            [⚠️ 系统强制修正指令 / CRITICAL FEEDBACK]
            上一次生成的内容未通过质量审核。
            遗漏点：{missing_points}
            专家修改建议：{suggestions}
            
            请务必基于上述建议重新生成回答！
            =========================================
            """
            
            # (3) 重新调用 Agent
            retry_result = await llm_service.process_agent_request(
                prompt=request.prompt,
                context=request.context,
                reference_info=retry_reference_info, # 注入了修正意见
                history=request.history
            )
            
            # (4) 覆盖结果
            print("--- [Retry] 修正完成，覆盖旧结果 ---")
            final_reply_text = retry_result.get("reply")
            final_modified_data = retry_result.get("modified_data")

        # === 5. 返回最终结果 ===
        return AgentResponse(
            intention=final_intention,
            reply=final_reply_text,
            modified_data=final_modified_data
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))