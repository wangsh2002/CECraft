from langchain_community.chat_models import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.core.config import settings
import json
from app.services.format_converter import delta_to_markdown, markdown_to_delta

# ================= 0. SUMMARY PROMPT (新增：摘要记忆) =================
SUMMARY_SYSTEM_PROMPT = """
你是对话摘要助手。
请将对话历史总结为简洁摘要，保留关键信息（背景、技能、意向、修改点）。
不含寒暄，直接陈述事实。
"""

# ================= 1. SUPERVISOR PROMPT (核心修改：细分意图) =================
SUPERVISOR_SYSTEM_PROMPT = """
你是简历系统总控。分析指令并路由：

1. **research_consult**: 仅询问外部信息（薪资、面试题、行情），**无**修改简历意图。
2. **research_modify**: 需修改简历，且涉及：
   - **外部信息**: JD、市场热点、公司要求。
   - **专业方法**: STAR法则、简历范文、高分模板。
3. **modify**: 仅基于**现有内容**的简单修改（润色、翻译、纠错、改格式），**不涉及**上述外部信息或专业方法。
4. **chat**: 闲聊、问候或无法归类。

摘要: {summary}
指令: {input}

输出JSON:
{{
    "next_agent": "research_consult" | "research_modify" | "modify" | "chat",
    "reasoning": "简短理由",
    "search_query": "关键词(仅research_*需)"
}}
"""

# ================= 2. AGENT PROMPT (核心修改：增加参考信息逻辑) =================
AGENT_SYSTEM_PROMPT = """
简历优化助手。
任务: 分析指令{user_prompt}，参考{reference_info}，修改简历{context_json}。
规则:
- 结合参考信息修改。
- 严禁改专有名词、公司、数字。
- 保持Markdown格式。**仅对技术名词（如Java, Docker）、核心量化数据（如50%, 100万）、关键专有名词**进行特殊格式处理，严禁对普通动词、形容词或整句进行特殊格式处理。

输出JSON:
{{
    "intention": "modify",
    "reply": "说明",
    "modified_content": "Markdown内容"
}}
"""

REVIEW_SYSTEM_PROMPT = """
资深招聘专家。诊断简历片段。
维度: 量化成果、动作力度、排版逻辑。

输出JSON:
{{
    "score": 85,
    "summary": "专业点评",
    "pros": ["亮点"],
    "cons": ["不足"],
    "suggestions": ["建议"]
}}
"""

CHAT_SYSTEM_PROMPT = """
AI简历助手。帮助修改简历、诊断和提供建议。
摘要: {summary}
输出JSON包含"reply"。
"""

EVALUATION_SYSTEM_PROMPT = """
评估Agent回复是否满足用户需求。
标准: 意图一致，准确无幻觉，格式正确。
核心任务完成且无严重错误即通过(is_pass: true)。

输入:
指令: {user_prompt}
参考: {reference_info}
回复: {agent_reply}
数据: {modified_data_snippet}

输出JSON:
{{
    "is_pass": true/false,
    "score": 0-100,
    "missing_points": ["遗漏"],
    "reason": "理由",
    "suggestion": "建议"
}}
"""
# ================= SERVICE CLASS =================

class LLMService:
    def __init__(self):
        # 1. 初始化 Lite 模型 (用于摘要、简单分类)
        self.llm_lite = ChatOpenAI(
            model=settings.LLM_MODEL_LITE,
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.OPENAI_API_BASE,
            temperature=0.1,
        )
        
        # 2. 初始化 Pro 模型 (用于生成、推理、复杂指令)
        self.llm_pro = ChatOpenAI(
            model=settings.LLM_MODEL_PRO,
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.OPENAI_API_BASE,
            temperature=0.1,
        )
        
        # 3. 默认 LLM (指向 Pro，保证默认高质量)
        self.llm = self.llm_pro
        
        self.parser = JsonOutputParser()
        self._init_chains()

    def _init_chains(self):
        # 0. Summary Chain (使用 Lite 模型)
        summary_prompt = ChatPromptTemplate.from_messages([
            ("system", SUMMARY_SYSTEM_PROMPT),
            ("user", "{conversation}")
        ])
        self.summary_chain = summary_prompt | self.llm_lite | StrOutputParser()

        # 1. Supervisor Chain (使用 Pro 模型，保证意图识别准确)
        supervisor_prompt = ChatPromptTemplate.from_messages([
            ("system", SUPERVISOR_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}")
        ])
        self.supervisor_chain = supervisor_prompt | self.llm_pro | self.parser

        # 2. Modify Agent Chain (核心修改：模版增加 reference_info)
        agent_prompt = ChatPromptTemplate.from_messages([
            ("system", AGENT_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "用户的指令：{user_prompt}\n参考信息：{reference_info}\n上下文内容：{context_json}")
        ])
        self.agent_chain = agent_prompt | self.llm_pro | self.parser

        # 3. Review Agent Chain
        review_prompt = ChatPromptTemplate.from_messages([
            ("system", REVIEW_SYSTEM_PROMPT),
            ("user", "请诊断以下简历内容：\n{resume_content}")
        ])
        self.review_chain = review_prompt | self.llm_pro | self.parser

        # 4. Chat Agent Chain
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", CHAT_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "用户输入：{user_input}\n\n当前简历内容（供参考）：\n{context}")
        ])
        self.chat_chain = chat_prompt | self.llm_pro | self.parser

        # 5. Evaluation Chain (质检链)
        eval_prompt = ChatPromptTemplate.from_messages([
            ("system", EVALUATION_SYSTEM_PROMPT),
            ("user", """
            [用户原始指令]
            {user_prompt}

            [参考信息]
            {reference_info}

            [Agent 生成的回复]
            {agent_reply}

            [修改后的数据片段 (前 2000 字符)]
            {modified_data_snippet}
            
            请开始评估：
            """)
        ])
        # 管道：Prompt -> LLM -> JSON Parser
        self.evaluation_chain = eval_prompt | self.llm_pro | self.parser

    # === Methods ===

    async def _process_history_with_strategy(self, raw_history: list) -> dict:
        """
        综合处理历史记录：
        1. 结构化转换 (Dict -> Message)
        2. 滑动窗口 (保留最近 N 条)
        3. 摘要生成 (如果历史过长)
        """
        WINDOW_SIZE = 6  # 保留最近 6 条对话 (3轮)
        SUMMARY_THRESHOLD = 10 # 如果超过 10 条，触发摘要生成
        
        if not raw_history:
            return {"summary": "无", "chat_history": []}

        # 1. 分离新旧历史
        recent_history = raw_history[-WINDOW_SIZE:]
        older_history = raw_history[:-WINDOW_SIZE]
        
        # 2. 转换最近历史为 Message 对象
        chat_messages = []
        for msg in recent_history:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                chat_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                chat_messages.append(AIMessage(content=content))
        
        # 3. 处理摘要 (如果历史很长)
        summary_text = "无"
        if len(raw_history) > SUMMARY_THRESHOLD and older_history:
            # 为了性能，我们只对 older_history 进行摘要
            # 将 older_history 格式化为文本
            conversation_text = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in older_history])
            try:
                # 异步生成摘要
                summary_text = await self.summary_chain.ainvoke({"conversation": conversation_text})
            except Exception as e:
                print(f"Summary Generation Error: {e}")
                summary_text = "无法生成摘要"

        return {"summary": summary_text, "chat_history": chat_messages}

    async def process_supervisor_request(self, prompt: str, history: list = []):
        try:
            processed = await self._process_history_with_strategy(history)
            return await self.supervisor_chain.ainvoke({
                "input": prompt, 
                "chat_history": processed["chat_history"],
                "summary": processed["summary"]
            })
        except Exception as e:
            print(f"Supervisor Error: {e}")
            # Fallback to chat if supervisor fails
            return {"next_agent": "chat", "reasoning": "Supervisor failed, fallback to chat.", "search_query": ""}

    async def process_chat_request(self, prompt: str, context: str = "", history: list = []):
        try:
            # 1. 预处理：将 context (Delta) 转为 Markdown
            context_data = {}
            try:
                context_data = json.loads(context)
            except:
                pass
            
            # 假设 context 是包含 content 的字典
            original_content = context
            if isinstance(context_data, dict) and "content" in context_data:
                original_content = context_data["content"]
            
            # 转换 content 为 Markdown
            markdown_context = delta_to_markdown(original_content)
            
            # Fallback
            if not markdown_context and original_content:
                if isinstance(original_content, (dict, list)):
                    markdown_context = json.dumps(original_content, ensure_ascii=False)
                else:
                    markdown_context = str(original_content)

            processed = await self._process_history_with_strategy(history)
            return await self.chat_chain.ainvoke({
                "user_input": prompt, 
                "context": markdown_context,
                "chat_history": processed["chat_history"],
                "summary": processed["summary"]
            })
        except Exception as e:
            print(f"Chat Error: {e}")
            return {"reply": "抱歉，我现在无法回答您的问题，请稍后再试。"}

    async def process_review_request(self, resume_content: str):
        try:
            return await self.review_chain.ainvoke({"resume_content": resume_content})
        except Exception as e:
            print(f"Review Error: {e}")
            return {"score": 0, "summary": "诊断服务暂时不可用", "pros": [], "cons": [], "suggestions": []}

    # [核心修改]：改为 async，增加 reference_info 参数
    async def process_agent_request(self, prompt: str, context: str, reference_info: str = "无", history: list = []):
        """调用修改 Agent"""
        try:
            # 1. 预处理：将 context (Delta) 转为 Markdown
            context_data = {}
            try:
                context_data = json.loads(context)
            except:
                pass
            
            # 假设 context 是包含 content 的字典
            original_content = context
            if isinstance(context_data, dict) and "content" in context_data:
                original_content = context_data["content"]
            
            # 转换 content 为 Markdown
            markdown_context = delta_to_markdown(original_content)
            
            # Fallback: 如果转换结果为空但原始内容不为空，直接使用原始内容字符串
            if not markdown_context and original_content:
                print("⚠️ [Agent] delta_to_markdown returned empty. Falling back to raw content.")
                if isinstance(original_content, (dict, list)):
                    markdown_context = json.dumps(original_content, ensure_ascii=False)
                else:
                    markdown_context = str(original_content)
            
            # 如果 context 是字典，更新 content 字段以便 LLM 看到其他元数据
            if isinstance(context_data, dict):
                context_data["content"] = markdown_context
                context_input = json.dumps(context_data, ensure_ascii=False)
            else:
                context_input = markdown_context

            processed = await self._process_history_with_strategy(history)
            
            # 2. 调用 LLM
            res = await self.agent_chain.ainvoke({
                "user_prompt": prompt,
                "context_json": context_input, # 传入 Markdown
                "reference_info": reference_info,  # 将搜索结果传入 Prompt
                "chat_history": processed["chat_history"],
                "summary": processed["summary"]
            })
            
            # 3. 后处理：将 Markdown 转回 Delta
            modified_content_md = res.get("modified_content", "")
            modified_data = None
            
            if modified_content_md:
                delta_json = markdown_to_delta(modified_content_md)
                modified_data = json.loads(delta_json) # 转为对象返回
            
            return {
                "intention": "modify",
                "reply": res.get("reply", ""),
                "modified_data": modified_data
            }
        except Exception as e:
            print(f"Agent Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "intention": "modify",
                "reply": "抱歉，处理您的请求时遇到错误，请重试。",
                "modified_data": None
            }
    
    # [接口] 执行评估
    async def process_evaluation_request(self, user_prompt: str, agent_reply: str, reference_info: str = "无", modified_data: dict = None):
        """
        返回结构化的评估结果 (JSON Dict)
        """
        # 提取 modified_data 的摘要 (避免 Token 爆炸)
        modified_data_snippet = "无修改数据"
        if modified_data:
            # 将 modified_data 转换为字符串，并截取前 2000 个字符
            # 现在的 modified_data 是 DeltaSet (dict)，直接转字符串即可
            ops_str = str(modified_data)
            if len(ops_str) > 2000:
                modified_data_snippet = ops_str[:2000] + "... (truncated)"
            else:
                modified_data_snippet = ops_str

        try:
            return await self.evaluation_chain.ainvoke({
                "user_prompt": user_prompt,
                "agent_reply": agent_reply,
                "reference_info": reference_info,
                "modified_data_snippet": modified_data_snippet
            })
        except Exception as e:
            print(f"Evaluation Logic Error: {e}")
            # 降级处理：如果评估崩了，默认通过，避免卡死流程
            return {"is_pass": True, "score": 0, "reason": "评估服务异常", "missing_points": []}

llm_service = LLMService()