AI 简历优化助手 - 技术实现文档
1. 功能概述
AI 简历优化助手允许用户选中简历中的文本模块，输入优化指令（如“把这段经历改得更专业”），由后端 AI Agent 生成修改后的富文本数据。前端提供预览功能，确认无误后将修改应用到画布上。

2. 后端接口规范
该功能基于 FastAPI 实现，集成了通义千问（DashScope）大模型。

接口定义

接口地址: /api/ai/agent

请求方法: POST

Content-Type: application/json

请求参数 (Request Body)

字段名	类型	必填	说明
prompt	string	是	用户的指令，例如："优化这段工作经历的描述"。
context	string	是	当前选中文本块的上下文数据。通常是序列化后的 JSON 字符串，包含原有的文本内容和格式。
请求示例:

JSON
{
  "prompt": "请帮我润色这段自我介绍，使其更自信。",
  "context": "{\"chars\":[{\"char\":\"我\",\"config\":{\"WEIGHT\":\"bold\"}}...]}"
}
响应参数 (Response Body)

后端会返回一个 JSON 对象，包含意图识别结果和标准化的 Delta 数据。

字段名	类型	说明
intention	string	AI 识别的意图。"modify" 表示需要修改内容，"chat" 表示普通对话。
reply	string	AI 给用户的文本回复/解释。
modified_data	object	null
响应示例 (Modify 意图):

JSON
{
  "intention": "modify",
  "reply": "已为您优化自我介绍，突出了您的领导能力。",
  "modified_data": {
    "ops": [
      { "insert": "拥有 5 年前端架构经验", "attributes": { "bold": true, "fontSize": 14 } },
      { "insert": "\n", "attributes": { "list": "bullet" } }
    ]
  }
}
数据格式规范 (重要)

为了兼容前端编辑器（BlockKit），后端通过 Prompt Engineering 强制 AI 输出 Quill Delta 格式，并执行以下属性映射：

数据结构: 必须包含 ops 数组。

属性映射:

WEIGHT: "bold" -> attributes: { "bold": true }

SIZE: 14 -> attributes: { "fontSize": 14 }

UNORDERED_LIST_LEVEL -> attributes: { "list": "bullet" } (注意：列表属性仅附加在 \n 上)

3. 前端集成与使用指南
前端位于右侧面板 (RightPanel)，负责采集上下文、调用接口以及最关键的数据格式转换。

3.1 调用流程图

采集: 用户选中 Text 节点 -> 获取内部格式数据 (RichTextLines)。

发送: 将数据序列化为字符串 -> 发送 POST /api/ai/agent。

预览: 接收 Quill Delta (modified_data) -> 在 Modal 中渲染预览。

转换 (关键): 用户点击“应用” -> Quill Delta 转回 RichTextLines。

应用: 将转换后的数据写入 editor.state。

3.2 关键代码实现

步骤 1: 发送请求 (RightPanel)

在 handleAISubmit 中，获取当前选中文本的状态数据并发送。

TypeScript
// CECraft/frontend/packages/react/src/components/right-panel/index.tsx

const handleAISubmit = async (value: string) => {
  // 1. 获取原始 Sketch 数据
  const rawDeltaData = activeState.getAttr(TEXT_ATTRS.DATA);
  const contextStr = typeof rawDeltaData === 'object' ? JSON.stringify(rawDeltaData) : rawDeltaData;

  // 2. 调用 API
  const response = await fetch("/api/ai/agent", {
    method: "POST",
    body: JSON.stringify({ prompt: value, context: contextStr }),
    // ... headers
  });
  
  const result = await response.json();
  if (result.intention === "modify") {
    setPreviewData(result.modified_data); // 保存 Quill Delta 格式用于预览
    setShowPreview(true);
  }
};
步骤 2: 预览数据 (AIPreviewModal)

在预览组件中，需要识别后端返回的 ops 格式并直接渲染，跳过针对 Sketch 格式的转换逻辑。

TypeScript
// CECraft/frontend/packages/react/src/components/right-panel/components/ai-preview/index.tsx
import { Delta as BlockDelta } from "@block-kit/delta";

useMemo(() => {
  if (modifiedData && Array.isArray(modifiedData.ops)) {
    // 识别到标准 Quill Delta 格式，直接实例化
    dataRef.current = new BlockDelta(modifiedData.ops);
  } else {
    // 兼容旧逻辑
    dataRef.current = sketchToTextDelta(modifiedData);
  }
}, [modifiedData]);
步骤 3: 应用修改与格式回转 (handleApplyModification)

这是防止崩溃的核心步骤。编辑器内核（Sketching Core）不认识 Quill Delta 格式，必须在应用前转换回内部格式。

引入依赖:

TypeScript
import { Delta as BlockDelta } from "@block-kit/delta";
import { textDeltaToSketch } from "./components/text/utils/transform";
import { TSON } from "sketching-utils";
实现逻辑:

TypeScript
const handleApplyModification = () => {
  if (previewData && Array.isArray(previewData.ops)) {
    // 1. 实例化 Quill Delta 对象
    const blockDelta = new BlockDelta(previewData.ops);
    
    // 2. 核心转换：Quill Delta -> Sketch Internal Format (RichTextLines)
    const sketchData = textDeltaToSketch(blockDelta);
    
    // 3. 序列化并应用到画布状态
    const payload = TSON.stringify(sketchData);
    editor.state.apply(new Op(OP_TYPE.REVISE, { 
        id: activeState.id, 
        attrs: { [TEXT_ATTRS.DATA]: payload } 
    }));
  }
};
4. 常见问题排查
预览窗口空白:

检查后端返回的 modified_data 是否包含 ops 数组。

检查前端 AIPreviewModal 是否正确处理了 ops 格式（如上文 3.2 步骤 2 所示）。

点击应用后报错 undefined is not a function (near '...line of lines...'):

这是因为直接将 Quill Delta 对象存入了 Editor State。

解决: 必须确保 handleApplyModification 中调用了 textDeltaToSketch 将数据转换回数组格式。

列表样式丢失:

检查后端 Prompt，确认 list: bullet 属性是附加在 \n 字符上的，而不是文本字符上。