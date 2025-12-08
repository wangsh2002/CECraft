from langchain_community.chat_models import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.core.config import settings

# ================= 1. SUPERVISOR PROMPT (核心修改：细分意图) =================
SUPERVISOR_SYSTEM_PROMPT = """
你是智能简历系统的总控大脑 (Supervisor)。你的任务是分析用户输入，将其路由到最合适的处理意图。

请严格从以下 **四个** 选项中选择一个：

1. **research_consult (调研咨询)**: 
    - 适用场景：用户**仅仅想查询**外部信息，如薪资范围、面试题、公司背景、行业趋势，但**没有**明确表达要修改简历。
    - 关键词：查一下、是多少、什么要求、面试题、薪资、行情、调研。
    - 示例："帮我查一下现在 Python 后端的薪资"、"字节跳动的面试风格是怎样的"。

2. **research_modify (调研并修改)**: 
    - 适用场景：用户希望**利用搜索到的外部信息来优化或修改**简历。通常包含“根据...修改”、“对标...优化”、“参考...调整”等指令。
    - 关键词：根据JD修改、对标大厂优化、参考这个链接润色、结合行情调整。
    - 示例："根据现在市场上 Java 高级的要求，帮我优化技能列表"、"帮我看看这个岗位链接，然后针对性修改我的简历"。

3. **modify (直接修改)**: 
    - 适用场景：用户指令明确，**不需要**外部信息辅助，直接对简历内容进行润色、精简、翻译或纠错。
    - 关键词：润色这段话、改短一点、翻译成英文、纠正错别字。

4. **chat (闲聊)**: 
    - 适用场景：问候、功能询问、通用建议，不涉及具体的搜索或修改动作。

### 输出格式
请务必直接输出一个合法的 JSON 对象。
JSON 对象必须包含以下两个字段：
- "next_agent": 必须是 "research_consult", "research_modify", "modify", 或 "chat" 之一。
- "reasoning": 简要说明做出该判断的理由。
"""

# ================= 2. AGENT PROMPT (核心修改：增加参考信息逻辑) =================
AGENT_SYSTEM_PROMPT = """
你是一个专业的简历优化助手和数据处理 Agent。

### 任务目标
1. 分析用户的指令。
2. 参考提供的上下文内容 (简历原始数据)。
3. **结合提供的参考信息 (如JD、行业调研数据) 进行针对性优化**。
4. 将修改后的内容转换为标准的 Quill Delta 格式输出。

### 输入数据说明
- 用户指令: {user_prompt}
- 参考信息 (外部知识): {reference_info}
- 上下文内容 (简历原件): {context_json}

### 处理逻辑
- **如果有参考信息**：请提取其中的关键词、技能要求或风格，对简历内容进行润色或重写，使其更匹配参考信息。
- **如果没有参考信息**：则仅根据用户指令进行常规修改。

### ⚠️ 内容保持与格式约束 (重要)
1. **结构保持**：请尽量**保持原有的段落数量、换行结构**。
2. **空格保留**：文本中的对齐空格请**务必原样保留**。
3. **英文规范**：**严禁**在英文单词内部插入错误的空格。

### Delta 格式严格要求
修改后的数据 (modified_data) 必须是一个包含 "ops" 数组的对象。
**关键：请务必将原始属性转换为标准的 Quill/BlockKit 属性 (bold, fontSize, color, list)，不要保留原始业务字段。**

### 输出示例
{{
    "intention": "modify",
    "reply": "根据为您查找到的JD要求，已重点突出了并发编程经验。",
    "modified_data": {{"ops": [...] }}
}}

### 你的输出
请只输出一个合法的 JSON 对象，不要包含 Markdown 标记。
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
请输出 JSON 格式，包含 "reply" 字段。
"""

# ================= SERVICE CLASS =================

class LLMService:
    def __init__(self):
        self.llm = ChatTongyi(
            model="qwen-flash",
            dashscope_api_key=settings.DASHSCOPE_API_KEY,
            temperature=0.1,
        )
        self.parser = JsonOutputParser()
        self._init_chains()

    def _init_chains(self):
        # 1. Supervisor Chain
        supervisor_prompt = ChatPromptTemplate.from_messages([
            ("system", SUPERVISOR_SYSTEM_PROMPT),
            ("user", "{input}")
        ])
        self.supervisor_chain = supervisor_prompt | self.llm | self.parser

        # 2. Modify Agent Chain (核心修改：模版增加 reference_info)
        agent_prompt = ChatPromptTemplate.from_messages([
            ("system", AGENT_SYSTEM_PROMPT),
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
            ("user", "{user_input}")
        ])
        self.chat_chain = chat_prompt | self.llm | self.parser

    # === Methods ===

    async def process_supervisor_request(self, prompt: str):
        return await self.supervisor_chain.ainvoke({"input": prompt})

    async def process_chat_request(self, prompt: str):
        return await self.chat_chain.ainvoke({"user_input": prompt})

    async def process_review_request(self, resume_content: str):
        return await self.review_chain.ainvoke({"resume_content": resume_content})

    # [核心修改]：改为 async，增加 reference_info 参数
    async def process_agent_request(self, prompt: str, context: str, reference_info: str = "无"):
        """调用修改 Agent"""
        return await self.agent_chain.ainvoke({
            "user_prompt": prompt,
            "context_json": context,
            "reference_info": reference_info  # 将搜索结果传入 Prompt
        })

llm_service = LLMService()