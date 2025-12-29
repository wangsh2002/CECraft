import json
import asyncio
from typing import TypedDict, List, Annotated, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, SystemMessage

from app.services.agent_workflow import llm_service
from app.services.tools.rag_retriever import search_and_rerank
from app.services.tools.web_search import perform_web_search

class AgentState(TypedDict):
    # Inputs
    user_input: str
    context_json: str
    history: List[dict]
    block_size: Dict[str, float]
    
    # Internal State
    next_step: str
    search_query: str
    reference_info: str
    
    # Evaluation State
    retry_count: int
    evaluation_feedback: str
    is_pass: bool
    
    # Output
    final_response: Dict[str, Any]

async def supervisor_node(state: AgentState):
    print("--- Supervisor Node ---")
    user_input = state["user_input"]
    history = state.get("history", [])
    
    try:
        decision = await llm_service.process_supervisor_request(user_input, history)
    except Exception as e:
        print(f"Supervisor Error: {e}")
        # Fallback to chat if supervisor fails
        decision = {"next_agent": "chat", "search_query": ""}
    
    return {
        "next_step": decision.get("next_agent", "chat"),
        "search_query": decision.get("search_query") or user_input
    }

async def research_node(state: AgentState):
    print("--- Research Node ---")
    query = state["search_query"]
    
    if not query:
        print("⚠️ [Research] Search query is empty. Skipping research.")
        return {"reference_info": "未提供搜索关键词，无法进行调研。"}

    # --- Tool Router Logic ---
    # Decide whether to use Web Search, RAG, or Both
    print(f"--- [ToolRouter] Analyzing query: {query} ---")
    
    router_prompt = (
        f"分析查询: '{query}'\n"
        f"选择最佳信息源:\n"
        f"- 'web': 需要实时/外部信息 (JD、薪资、公司新闻、市场行情)。\n"
        f"- 'rag': 需要方法论/内部知识 (STAR法则、简历模板、写作技巧)。\n"
        f"- 'both': 明确需要**同时**结合外部数据和内部方法论。\n"
        f"仅输出一个词: 'web', 'rag', 或 'both'。"
    )
    
    try:
        # Use the LLM from llm_service directly
        router_response = await llm_service.llm.ainvoke([HumanMessage(content=router_prompt)])
        tool_choice = router_response.content.strip().lower()
    except Exception as e:
        print(f"Tool Router Error: {e}. Defaulting to 'both'.")
        tool_choice = "both"
        
    print(f"--- [ToolRouter] Choice: {tool_choice} ---")
    
    # Execute tasks using a dictionary for better management
    tasks = {}
    if "rag" in tool_choice or "both" in tool_choice:
        tasks["rag"] = asyncio.to_thread(search_and_rerank, query)
        
    if "web" in tool_choice or "both" in tool_choice:
        tasks["web"] = perform_web_search(query)
    
    results = {}
    if tasks:
        # Run tasks concurrently
        task_names = list(tasks.keys())
        task_coroutines = list(tasks.values())
        
        # return_exceptions=True ensures one failure doesn't crash the others
        task_results = await asyncio.gather(*task_coroutines, return_exceptions=True)
        
        for name, res in zip(task_names, task_results):
            results[name] = res
            
    # Process Results
    rag_text = ""
    web_text = ""
    
    if "rag" in results:
        res = results["rag"]
        if isinstance(res, list):
            rag_text = "\n".join([d.get('text', '') for d in res])
        elif isinstance(res, Exception):
            print(f"RAG Error: {res}")
            rag_text = "RAG 检索失败"
            
    if "web" in results:
        res = results["web"]
        if isinstance(res, str):
            web_text = res
        elif isinstance(res, Exception):
            print(f"Web Search Error: {res}")
            web_text = "Web 搜索失败"
            
    combined_info = ""
    if rag_text:
        combined_info += f"**RAG Context:**\n{rag_text}\n\n"
    if web_text:
        combined_info += f"**Web Search:**\n{web_text}"
        
    if not combined_info:
        combined_info = "未找到相关信息。"
    
    return {"reference_info": combined_info}

async def modify_node(state: AgentState):
    print("--- Modify Node (Drafter) ---")
    user_input = state["user_input"]
    context_json = state["context_json"]
    reference_info = state.get("reference_info", "无")
    history = state.get("history", [])
    block_size = state.get("block_size")
    intent = state.get("next_step", "modify") # 获取意图
    
    # Handle Retry Logic
    feedback = state.get("evaluation_feedback")
    if feedback:
        retry_cnt = state.get("retry_count", 0)
        print(f"--- [Retry] Injecting Feedback (Count: {retry_cnt}) ---")
        reference_info = f"""
        {reference_info}
        
        [REFLECTIVE RETRY]
        上次未通过审核。反馈：{feedback}
        请反思并重新生成 "reply" 和 "modified_data"。
        """
    
    res = await llm_service.process_agent_request(user_input, context_json, reference_info, history, block_size, intent=intent)
    
    # Format for API response
    final_res = {
        "intention": res.get("intention", "modify"), # 使用返回的 intention
        "reply": res.get("reply", ""),
        "modified_data": res.get("modified_data", {})
    }
    return {"final_response": final_res}

async def evaluation_node(state: AgentState):
    print("--- Evaluation Node (Reviewer) ---")
    user_input = state["user_input"]
    final_res = state["final_response"]
    reference_info = state.get("reference_info", "无")
    
    agent_reply = final_res.get("reply", "")
    modified_data = final_res.get("modified_data", {})
    
    eval_result = await llm_service.process_evaluation_request(
        user_prompt=user_input,
        agent_reply=agent_reply,
        reference_info=reference_info,
        modified_data=modified_data
    )
    
    is_pass = eval_result.get("is_pass", True)
    score = eval_result.get("score", 0)
    print(f"Evaluation Result: {'✅ PASS' if is_pass else '❌ FAIL'} (Score: {score})")
    
    feedback = ""
    if not is_pass:
        suggestions = eval_result.get("suggestion", "请检查用户需求是否满足")
        missing_points = ", ".join(eval_result.get("missing_points", []))
        feedback = f"遗漏点：{missing_points}\n专家修改建议：{suggestions}"
        
    return {
        "is_pass": is_pass,
        "evaluation_feedback": feedback,
        "retry_count": state.get("retry_count", 0) + 1
    }

async def formatter_node(state: AgentState):
    print("--- Formatter Node ---")
    # Ensure the final response is in the correct format
    final_res = state.get("final_response", {})
    
    intention = final_res.get("intention", "chat")
    
    # [重要修改] 前端目前仅识别 "modify" 意图来触发预览/应用窗口
    # 因此，将 "create" 意图映射为 "modify"
    if intention == "create":
        intention = "modify"
    
    # Default structure
    formatted_res = {
        "intention": intention,
        "reply": final_res.get("reply", ""),
        "modified_data": final_res.get("modified_data")
    }
    
    # If intention is modify/create but no modified_data, fallback to chat or log warning
    if formatted_res["intention"] == "modify" and not formatted_res["modified_data"]:
        print(f"⚠️ [Formatter] Intention is '{formatted_res['intention']}' but 'modified_data' is missing.")
        # Optionally change intention to chat if data is missing
        # formatted_res["intention"] = "chat"
        
    return {"final_response": formatted_res}

async def chat_node(state: AgentState):
    print("--- Chat Node ---")
    user_input = state["user_input"]
    history = state.get("history", [])
    reference_info = state.get("reference_info", "")
    context_json = state.get("context_json", "")
    
    # If we have reference info (from research_consult), append it to prompt
    prompt = user_input
    if reference_info:
        prompt = f"用户问题: {user_input}\n\n参考资料 (基于你的调研):\n{reference_info}\n\n请根据参考资料回答。"
        
    res = await llm_service.process_chat_request(prompt, context=context_json, history=history)
    
    final_res = {
        "intention": "chat",
        "reply": res.get("reply", ""),
        "modified_data": None
    }
    return {"final_response": final_res}

# Edge Logic
def route_after_supervisor(state: AgentState):
    intent = state["next_step"]
    if intent in ["research_consult", "research_modify", "research_create"]:
        return "research"
    elif intent in ["modify", "create"]:
        return "modify"
    else:
        return "chat"

def route_after_research(state: AgentState):
    intent = state["next_step"]
    if intent in ["research_modify", "research_create"]:
        return "modify"
    else:
        return "chat" # research_consult goes to chat to summarize findings

def route_after_evaluation(state: AgentState):
    if state.get("is_pass", True):
        return "formatter"
    if state.get("retry_count", 0) > 0: # Max 0 retries (1 attempt total)
        print("--- Max Retries Reached ---")
        return "formatter" # Fallback to formatter even if failed
    return "modify"

# Build Graph
workflow = StateGraph(AgentState)

workflow.add_node("supervisor", supervisor_node)
workflow.add_node("research", research_node)
workflow.add_node("modify", modify_node)
workflow.add_node("chat", chat_node)
workflow.add_node("evaluation", evaluation_node)
workflow.add_node("formatter", formatter_node)

workflow.set_entry_point("supervisor")

workflow.add_conditional_edges(
    "supervisor",
    route_after_supervisor,
    {
        "research": "research",
        "modify": "modify",
        "chat": "chat"
    }
)

workflow.add_conditional_edges(
    "research",
    route_after_research,
    {
        "modify": "modify",
        "chat": "chat"
    }
)

workflow.add_edge("modify", "evaluation")
workflow.add_conditional_edges(
    "evaluation",
    route_after_evaluation,
    {
        "formatter": "formatter",
        "modify": "modify"
    }
)
workflow.add_edge("formatter", END)
workflow.add_edge("chat", END)

checkpointer = MemorySaver()
app_graph = workflow.compile(checkpointer=checkpointer)
