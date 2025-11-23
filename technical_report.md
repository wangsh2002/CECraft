CECraft AI 智能助手集成技术报告

1. 概述

本报告详细阐述了在 CECraft 简历编辑器中集成 AI 智能助手（Agent）的技术实现。系统利用通义千问（qwen-flash）大模型，实现了基于意图识别的富文本简历内容自动优化与即时预览功能。

2. 架构设计

2.1 整体流程

用户交互：用户在前端 Canvas 选中富文本节点 -> 输入自然语言指令。

数据组装：前端提取当前节点的 Delta JSON 数据 + 用户指令，发送至后端。

后端 Agent 处理：

Intent Classifier (意图识别)：判断是 "modify" (修改) 还是 "chat" (闲聊)。

Content Generation (内容生成)：如果是修改，生成符合 Quill/Delta 规范的 JSON 数据。

前端反馈：

显示 AI 文本回复。

如果包含修改数据，显示 "预览修改" 按钮。

预览与应用：用户点击预览 -> 弹出带渲染的模态框 -> 点击应用 -> 更新 Canvas 状态。

2.2 接口规范 (API Specification)

Endpoint: POST /api/ai/agent

Request:

{
  "prompt": "把这段经历写得更专业一点",
  "context": "{\"chars\": [...]}" // 原始 Delta JSON 字符串
}


Response:

{
  "intention": "modify", // 或 "chat"
  "reply": "已为您优化了关于实习经历的描述，增强了动词力度。",
  "modified_data": { ... } // 新的 Delta JSON 对象，若 intention 为 chat 则为 null
}


3. 详细实现细节

3.1 后端 Agent 实现 (backend/main.py)

模型选择：使用 qwen-flash，该模型在长文本处理和 JSON 格式指令遵循上具有极高的性价比和速度。

Prompt Engineering：

使用了 System Prompt 来强约束输出格式。

明确要求输出必须是严格的 JSON，包含 intention, reply, modified_data 三个字段。

向 AI 解释了 Delta 格式（ops, insert, attributes），确保生成的 JSON 能被前端编辑器直接解析。

鲁棒性处理：增加了 JSON 解析容错机制，如果 AI 返回了 Markdown 代码块（```json），会自动清洗后解析。

3.2 前端交互实现 (frontend/.../right-panel)

A. 状态管理

在 RightPanel 组件中引入了新的状态：

previewData: 用于存储后端返回的待修改数据。

isLoading: 控制 UI 的加载与禁用状态。

showPreview: 控制预览模态框的显示。

B. 数据流转

发送前：使用 activeState.getAttr(TEXT_ATTRS.DATA) 获取原始结构化数据，而非纯文本。这保留了原有的样式信息，让 AI 能在原有格式基础上修改。

接收后：判断 intention === 'modify'。如果是，则不直接覆盖，而是存入临时状态，等待用户确认。

C. 预览组件 (AIPreviewModal)

复用性：该组件复用了项目原有的 RichTextEditor 模块。

数据转换：由于 RichTextEditor 通常依赖 useMemo 计算数据源，我们通过 useRef + sketchToTextDelta 工具函数，将 AI 返回的 JSON 转换为编辑器可渲染的 BlockDelta 格式。

隔离性：预览组件在 Modal 中运行，点击 "取消" 不会对 Canvas 产生任何副作用；只有点击 "应用" 才会触发 editor.state.apply。

4. 环境配置与部署

4.1 新建 Conda 环境

conda create -n cecraft_ai python=3.9
conda activate cecraft_ai
pip install -r backend/requirements.txt


4.2 启动服务

后端:

cd backend
python main.py
# 服务将运行在 [http://0.0.0.0:8000](http://0.0.0.0:8000)


前端:
确保前端代理或 Fetch URL 指向 localhost:8000。

5. 总结与改进方向

本次更新成功将简单的 AI 对话升级为具备“动作执行”能力的 Agent。

优势：所见即所得的修改预览，避免了 AI 幻觉直接破坏用户简历；严格的 JSON 约束保证了数据格式的安全性。

改进方向：

目前使用 qwen-flash 能够较好处理，但在极其复杂的富文本嵌套下，可能仍需微调 Prompt 以保证 attributes 的精准保留。

可以增加 "流式 diff" 功能，让用户直观看到修改了哪些字词。