from langchain_community.chat_models import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.core.config import settings

# ================= 0. SUMMARY PROMPT (新增：摘要记忆) =================
SUMMARY_SYSTEM_PROMPT = """
你是一个专业的对话摘要助手。
请将以下对话历史总结为一个简洁的摘要，保留关键信息（如用户的职业背景、技能、求职意向、已讨论的修改点）。
摘要不需要包含寒暄内容，直接陈述事实。
"""

# ================= 1. SUPERVISOR PROMPT (核心修改：细分意图) =================
SUPERVISOR_SYSTEM_PROMPT = """
你是智能简历系统的总控大脑 (Supervisor)。你的任务是分析用户输入，将其路由到最合适的处理意图。

### 上下文摘要 (长期记忆)
{summary}

### 输入信息
- 用户当前指令: {input}

请严格从以下 **四个** 选项中选择一个：

1. **research_consult (调研咨询)**: 
    - 适用场景：用户**仅仅想查询**外部信息，如薪资范围、面试题、公司背景、行业趋势，但**没有**明确表达要修改简历。
    - 关键词：查一下、是多少、什么要求、面试题、薪资、行情、调研、搜索。
    - 示例："帮我查一下现在 Python 后端的薪资"、"字节跳动的面试风格是怎样的"。

2. **research_modify (调研并修改)**: 
    - 适用场景：用户希望**利用搜索到的外部信息来优化或修改**简历。通常包含“根据...修改”、“对标...优化”、“参考...调整”等指令。
    - 关键词：根据JD修改、对标大厂优化、参考这个链接润色、结合行情调整、根据搜索结果修改。
    - 示例："根据现在市场上 Java 高级的要求，帮我优化技能列表"、"帮我看看这个岗位链接，然后针对性修改我的简历"。

3. **modify (直接修改)**: 
    - 适用场景：用户指令明确，**不需要**外部信息辅助，直接对简历内容进行润色、精简、翻译或纠错。
    - 关键词：润色这段话、改短一点、翻译成英文、纠正错别字、扩写。

4. **chat (闲聊)**: 
    - 适用场景：问候、功能询问、通用建议，不涉及具体的搜索或修改动作。
    - 注意：如果用户说 "继续"、"再改改" 等依赖上下文的指令，请结合对话历史判断其真实意图。

### 输出格式
请务必直接输出一个合法的 JSON 对象。
JSON 对象必须包含以下字段：
- "next_agent": 必须是 "research_consult", "research_modify", "modify", 或 "chat" 之一。
- "reasoning": 简要说明做出该判断的理由。
- "search_query": (可选) 如果意图是 research_*, 请生成一个优化后的搜索关键词（例如："Java后端 面试题"）。如果不需要搜索，返回空字符串。
"""

# ================= 2. AGENT PROMPT (核心修改：增加参考信息逻辑) =================
AGENT_SYSTEM_PROMPT = """
你是一个专业的简历优化助手和数据处理 Agent。

### 任务目标
1. 分析用户的指令。
2. 参考提供的上下文内容 (简历原始数据) 和对话历史。
3. **结合提供的参考信息 (如JD、行业调研数据) 进行针对性优化**。
4. 将修改后的内容转换为标准的 Quill Delta 格式输出。

### 上下文摘要 (长期记忆)
{summary}

### 输入数据说明
- 用户指令: {user_prompt}
- 参考信息 (外部知识): {reference_info}
- 上下文内容 (简历原件): {context_json}

### 处理逻辑
- **如果有参考信息**：请提取其中的关键词、技能要求或风格，对简历内容进行润色或重写，使其更匹配参考信息。
- **如果没有参考信息**：则仅根据用户指令进行常规修改。

### ⚠️ 内容保持与格式约束 (重要)
1. **富文本格式保留**：请务必保留原有的富文本格式（如加粗、颜色、字体大小等），除非用户明确要求修改格式。
2. **大段空格保留**：文本中用于对齐或排版的大段连续空格，请**务必原样保留**，不要合并或删除。
3. **结构保持**：**严禁**大幅度重构。必须保留主要的大体段落结构（段落数量、顺序、换行），避免改得面目全非。
4. **英文规范**：**严禁**在英文单词内部插入错误的空格。

### Delta 格式严格要求
修改后的数据 (modified_data) 必须是一个包含 "ops" 数组的对象。
**关键：请务必将原始属性转换为标准的 Quill/BlockKit 属性 (bold, fontSize, color, list)，不要保留原始业务字段。**

### 输出示例
{{
    "intention": "modify",
    "reflection": "（可选）自我反思...",
    "reply": "根据为您查找到的JD要求，已重点突出了并发编程经验。",
    "modified_data": {{"ops": [...] }}
}}

### 你的输出
请只输出一个合法的 JSON 对象，不要包含 Markdown 标记。如果无法生成有效的 JSON，请返回包含错误信息的 JSON。
"""

REVIEW_SYSTEM_PROMPT = """
你是一位拥有 15 年经验的资深技术招聘专家和简历顾问。
你的任务是根据用户提供的简历内容片段，进行深度的诊断和评估。

### 评估维度
1. **量化成果**：是否有具体的数字支撑（如提升了 50% 性能）。
2. **动作力度**：动词是否精准有力（如“负责” vs “主导/构建”）。
3. **排版与逻辑**：信息密度是否合适，阅读体验如何。

### 输出要求
请严格按照以下 JSON 格式输出：
{{
    "score": 85,
    "summary": "一句话的整体专业点评",
    "pros": ["亮点1", "亮点2"],
    "cons": ["不足1", "不足2"],
    "suggestions": ["修改建议1", "建议2"]
}}
"""

CHAT_SYSTEM_PROMPT = """
你是一个热情、专业且富有同理心的 AI 简历助手。
你的主要职责是帮助用户修改简历、进行简历诊断和提供职业建议。

### 上下文摘要 (长期记忆)
{summary}

请输出 JSON 格式，包含 "reply" 字段。
"""

EVALUATION_SYSTEM_PROMPT = """
你是一个严格的**回复质量评估专家 (Quality Assurance Auditor)**。
你的任务是评估前面的 Agent 生成的回复是否满足了用户的原始需求。

### 评估标准
1. **意图一致性**：回复内容是否直接响应了用户的指令？
2. **完整性**：如果用户问了两个问题，Agent 是否都回答了？
3. **准确性**：如果有参考信息 (Reference Info)，Agent 的回复是否与参考信息冲突？
4. **格式合规**：生成的 JSON 数据 (modified_data) 是否存在明显的逻辑错误？

### 评分规则
- **90-100分**：完美符合所有要求，格式正确，内容专业。
- **70-89分**：符合核心要求，但有轻微瑕疵（如语气不够完美，或遗漏次要细节）。
- **60-69分**：勉强及格，完成了主要任务，但存在明显不足。
- **0-59分**：未完成核心任务，或存在严重幻觉/格式错误。

**注意：只要 Agent 完成了用户的核心指令（如修改了简历、回答了问题），且没有严重错误，就应该给予及格分数（>60分）。不要因为“可以写得更好”而判为不及格。**

### 输入信息
- 用户原始指令 (User Prompt)
- 参考信息 (Reference Info)
- Agent 生成的回复 (Agent Reply)

### 输出格式 (严格 JSON)
请输出且仅输出一个 JSON 对象，包含以下字段：
{{
    "is_pass": true/false,   // 整体评估是否通过（60分以上为 true）
    "score": 85,             // 0-100 的评分
    "missing_points": [],    // 遗漏的用户需求点（数组，如果没有则为空）
    "reason": "...",         // 简短的评分理由
    "suggestion": "..."      // 如果不通过，给出的改进建议
}}
"""
# ================= SERVICE CLASS =================

class LLMService:
    def __init__(self):
        self.llm = ChatTongyi(
            model=settings.LLM_MODEL_NAME,
            dashscope_api_key=settings.DASHSCOPE_API_KEY,
            temperature=0.1,
        )
        self.parser = JsonOutputParser()
        self._init_chains()

    def _init_chains(self):
        # 0. Summary Chain (新增)
        summary_prompt = ChatPromptTemplate.from_messages([
            ("system", SUMMARY_SYSTEM_PROMPT),
            ("user", "{conversation}")
        ])
        self.summary_chain = summary_prompt | self.llm | StrOutputParser()

        # 1. Supervisor Chain
        supervisor_prompt = ChatPromptTemplate.from_messages([
            ("system", SUPERVISOR_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}")
        ])
        self.supervisor_chain = supervisor_prompt | self.llm | self.parser

        # 2. Modify Agent Chain (核心修改：模版增加 reference_info)
        agent_prompt = ChatPromptTemplate.from_messages([
            ("system", AGENT_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "用户的指令：{user_prompt}\n参考信息：{reference_info}\n上下文内容：{context_json}")
        ])
        self.agent_chain = agent_prompt | self.llm | self.parser

        # 3. Review Agent Chain
        review_prompt = ChatPromptTemplate.from_messages([
            ("system", REVIEW_SYSTEM_PROMPT),
            ("user", "请诊断以下简历内容：\n{resume_content}")
        ])
        self.review_chain = review_prompt | self.llm | self.parser

        # 4. Chat Agent Chain
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", CHAT_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{user_input}")
        ])
        self.chat_chain = chat_prompt | self.llm | self.parser

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
            
            请开始评估：
            """)
        ])
        # 管道：Prompt -> LLM -> JSON Parser
        self.evaluation_chain = eval_prompt | self.llm | self.parser

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

    async def process_chat_request(self, prompt: str, history: list = []):
        try:
            processed = await self._process_history_with_strategy(history)
            return await self.chat_chain.ainvoke({
                "user_input": prompt, 
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
            processed = await self._process_history_with_strategy(history)
            return await self.agent_chain.ainvoke({
                "user_prompt": prompt,
                "context_json": context,
                "reference_info": reference_info,  # 将搜索结果传入 Prompt
                "chat_history": processed["chat_history"],
                "summary": processed["summary"]
            })
        except Exception as e:
            print(f"Agent Error: {e}")
            return {
                "intention": "modify",
                "reply": "抱歉，处理您的请求时遇到错误，请重试。",
                "modified_data": None
            }
    
    # [接口] 执行评估
    async def process_evaluation_request(self, user_prompt: str, agent_reply: str, reference_info: str = "无"):
        """
        返回结构化的评估结果 (JSON Dict)
        """
        try:
            return await self.evaluation_chain.ainvoke({
                "user_prompt": user_prompt,
                "agent_reply": agent_reply,
                "reference_info": reference_info
            })
        except Exception as e:
            print(f"Evaluation Logic Error: {e}")
            # 降级处理：如果评估崩了，默认通过，避免卡死流程
            return {"is_pass": True, "score": 0, "reason": "评估服务异常", "missing_points": []}

llm_service = LLMService()