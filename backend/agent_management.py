from langchain_community.chat_models import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# 1. 配置 API Key
# (为了安全，建议以后放入环境变量，目前先放在这里)
DASHSCOPE_API_KEY = "sk-dd6029b7e0f4419ab4c5bab66d19e30a"

# 2. 初始化 LLM 模型
llm = ChatTongyi(
    model="qwen-flash",
    dashscope_api_key=DASHSCOPE_API_KEY,
    temperature=0.1,  # 低温度保证格式稳定
)

# 3. 初始化通用 JSON 解析器
parser = JsonOutputParser()

# ==========================================
# Agent A: 修改/润色 (Modify Agent)
# ==========================================
agent_system_prompt = """
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

agent_prompt_template = ChatPromptTemplate.from_messages([
    ("system", agent_system_prompt),
    ("user", "用户的指令：{user_prompt}\n上下文内容：{context_json}")
])

# 导出修改 Chain
agent_chain = agent_prompt_template | llm | parser


# ==========================================
# Agent B: 诊断/评分 (Review Agent)
# ==========================================
review_system_prompt = """
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

review_prompt_template = ChatPromptTemplate.from_messages([
    ("system", review_system_prompt),
    ("user", "请诊断以下简历内容：\n{resume_content}")
])

# 导出诊断 Chain
review_chain = review_prompt_template | llm | parser