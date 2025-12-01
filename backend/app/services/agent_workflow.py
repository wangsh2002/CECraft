from langchain_community.chat_models import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.core.config import settings

# ================= PROMPTS (保持原样) =================
SUPERVISOR_SYSTEM_PROMPT = """
你是智能简历系统的总控大脑 (Supervisor)。你的任务是分析用户输入，将其路由到最合适的处理意图 (Intention)。

请严格从以下三个选项中选择一个：

1. **research (调研模式)**: 
   - 适用场景：用户提供了 JD (职位描述)、职位链接、公司名称，或者明确要求“对标某岗位”、“针对某公司优化”、“寻找行业范例”等需要外部信息的情况。
   - 关键词：JD、链接、对标、调研、字节、腾讯、参考。

2. **modify (修改模式)**: 
   - 适用场景：用户明确要求对现有简历内容进行具体的修改、润色、翻译、精简或扩写，且不需要外部信息辅助。
   - 关键词：修改、润色、精简、翻译、改错别字、优化这段话。

3. **chat (闲聊模式)**: 
   - 适用场景：普通的问候、自我介绍、关于系统功能的咨询，或者与简历修改无直接关联的通用对话。
   - 关键词：你好、谢谢、你是谁、再见。

### 输出格式
请务必直接输出一个合法的 JSON 对象，不要包含 Markdown 标记（如 ```json ... ```）。
JSON 对象必须包含以下两个字段：
- "next_agent": 对应上面的选项值，必须是 "research", "modify", 或 "chat" 之一。
- "reasoning": 简要说明做出该判断的理由。

### 输出示例
{{
    "next_agent": "modify",
    "reasoning": "用户明确请求润色简历中的工作经历部分，不涉及外部JD。"
}}
"""

AGENT_SYSTEM_PROMPT = """
你是一个专业的简历优化助手和数据处理 Agent。

### 任务目标
1. 分析用户的指令。
2. 参考提供的上下文内容。
3. 判断用户意图是 "修改内容" (modify) 还是 "普通闲聊/提问" (chat)。
4. 如果是 "modify"，请根据用户指令修改内容，并**必须将其转换为标准的 Quill Delta 格式**输出。

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
    "reply": "已为您优化描述。",
    "modified_data": {{ "ops": [...] }}
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

### 注意事项
1. score 请打 0-100 的整数。
2. pros, cons, suggestions 必须是字符串数组。
3. 请只输出一个合法的 JSON 对象，不要包含 Markdown 标记。
"""

CHAT_SYSTEM_PROMPT = """
你是一个热情、专业且富有同理心的 AI 简历助手。
你的主要职责是帮助用户修改简历、进行简历诊断和提供职业建议。

### 你的任务
1. 回答用户的日常问候（如“你好”、“你是谁”）。
2. 解答关于你能力的问题（如“你能做什么”、“怎么帮我改简历”）。
3. 如果用户问了通用的求职问题，给出简短专业的建议。
4. 保持语气轻松愉快，鼓励用户开始优化简历。

### 输出格式
请务必直接输出一个合法的 JSON 对象，不要包含 Markdown 标记。
JSON 对象必须包含以下字段：
- "reply": 你的回复内容（字符串）。

### 输出示例
{{
    "intention": "chat",
    "reply": "你好呀！我是你的智能简历助手。我可以帮你润色简历措辞，或者对简历进行全方位的诊断。你可以直接把简历内容发给我哦！",
    "modified_data": {{ "ops": [...] }}
}}
"""

# ================= SERVICE CLASS =================

class LLMService:
    def __init__(self):
        # 初始化 LLM
        self.llm = ChatTongyi(
            model="qwen-flash",
            dashscope_api_key=settings.DASHSCOPE_API_KEY,
            temperature=0.1,  # 低温度保证格式稳定
        )
        self.parser = JsonOutputParser()
        self._init_chains()

    def _init_chains(self):
        # 1. Init supervisor Agent Chain
        supervisor_prompt = ChatPromptTemplate.from_messages([
            ("system", SUPERVISOR_SYSTEM_PROMPT),
            ("user", "{input}")
        ])
        self.supervisor_chain = supervisor_prompt | self.llm | self.parser

        # 2. Init Modify Agent Chain
        agent_prompt = ChatPromptTemplate.from_messages([
            ("system", AGENT_SYSTEM_PROMPT),
            ("user", "用户的指令：{user_prompt}\n上下文内容：{context_json}")
        ])
        self.agent_chain = agent_prompt | self.llm | self.parser

        # 3. Init Review Agent Chain
        review_prompt = ChatPromptTemplate.from_messages([
            ("system", REVIEW_SYSTEM_PROMPT),
            ("user", "请诊断以下简历内容：\n{resume_content}")
        ])
        self.review_chain = review_prompt | self.llm | self.parser

        # === 4. Init Chat Agent Chain ===
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", CHAT_SYSTEM_PROMPT),
            ("user", "{user_input}")
        ])
        self.chat_chain = chat_prompt | self.llm | self.parser

        #  大脑调用方法
    async def process_supervisor_request(self, prompt: str):
        """调用总控大脑进行路由"""
        # 使用 ainvoke 进行异步调用
        return await self.supervisor_chain.ainvoke({
            "input": prompt
        })
    
    def process_chat_request(self, prompt: str):
        """调用闲聊 Agent"""
        return self.chat_chain.invoke({
            "user_input": prompt
        })

    def process_agent_request(self, prompt: str, context: str):
        """调用修改 Agent"""
        return self.agent_chain.invoke({
            "user_prompt": prompt,
            "context_json": context
        })

    def process_review_request(self, resume_content: str):
        """调用诊断 Agent"""
        return self.review_chain.invoke({
            "resume_content": resume_content
        })

# 单例模式导出
llm_service = LLMService()