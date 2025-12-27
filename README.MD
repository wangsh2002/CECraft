# CECraft: Intelligent Resume Optimization System

**CECraft** 是一个集成了大语言模型（LLM）智能体与高性能富文本编辑器的简历优化平台。该系统旨在通过 Agentic Workflow（智能体工作流）解决非结构化简历数据与结构化岗位描述（JD）之间的语义匹配问题，利用 RAG（检索增强生成）技术实现简历内容的专业化重构、翻译与实时润色。

## 1. 系统概览

CECraft 采用前后端分离架构，前端基于 Canvas 引擎实现高性能渲染，后端基于 **LangGraph** 与 FastAPI 构建多智能体编排系统。

### 1.1 核心功能

* **多模态调研与咨询 (Deep Research)**：集成 Web Search 工具，支持针对薪资范围、面试题库及企业背景的外部信息检索。
* **岗位匹配与优化 (Targeted Optimization)**：解析目标岗位 JD，自动提取关键技能实体，调整简历的语义侧重以提升人岗匹配度。
* **基于 STAR 法则的重写 (Structure Transformation)**：自动将描述性文本重构为符合 "Situation-Task-Action-Result" 标准的专业履历。
* **专业级富文本编辑 (Canvas Editor)**：支持 Delta 数据结构、自定义插件系统及精确的打印布局控制。

### 1.2 智能体工作流 (Agentic Workflow)

系统采用基于 LangGraph 的多智能体协作模式：

* **总控大脑 (Supervisor)**：负责意图识别与路由，将请求分发至 ChatBot、Drafter 或 Researcher。
* **智能检索 (Researcher)**：内置工具路由 (ToolRouter)，根据查询意图自动选择 Web Search (联网搜索) 或 VectorDB (RAG 知识库)，并进行多源信息融合。
* **写作与质检闭环 (Drafter & Reviewer)**：
    * **Drafter**：负责草稿生成与修改。
    * **Reviewer**：对生成内容进行质量评估，若不合格则反馈修改意见，形成自我修正闭环。
* **格式化输出 (Formatter)**：确保最终响应符合标准 API 格式。

## 2. 技术架构深度解析

本项目重点解决了通用 LLM 在长上下文管理、领域知识检索及指令遵循稳定性方面的工程挑战。

### 2.1 检索增强生成 (Advanced RAG Pipeline)

为提升领域知识的召回精度，系统实现了全链路优化的 RAG 流水线：

* **两阶段检索 (Two-stage Retrieval)**：
* **召回层 (Retrieval)**：结合查询扩展 (Query Expansion) 生成多路子查询，通过混合检索 (Hybrid Search) 提升 Recall。
* **排序层 (Rerank)**：引入 **GTE-Rerank** (Cross-Encoder) 模型对向量召回结果进行语义精排，显著提升 Top-K 准确率。


* **结构化索引 (Structure-aware Indexing)**：
* **AST 切分**：基于 Markdown 抽象语法树解析文档，避免暴力切分导致的语义断裂。
* **父子索引 (Parent-Child Indexing)**：采用 "Small-to-Big" 策略，检索细粒度切片（Child Chunk）并映射回上下文完整的父文档（Parent Document），平衡检索粒度与生成质量。


* **动态检索 (Adaptive Retrieval)**：
* Supervisor 模块内置查询重写 (Query Rewriting) 逻辑，将用户自然语言转化为高信噪比的搜索关键词。



### 2.2 无状态上下文管理 (Stateless Context Management)

采用“前端托管 + 混合记忆”架构，解决服务端会话状态存储压力及 Token 上下文窗口限制：

* **RESTful 架构**：后端完全无状态，会话历史由客户端维护并按需注入，支持服务水平的线性扩展。
* **混合压缩策略 (Hybrid Memory)**：
* **滑动窗口 (Sliding Window)**：保留最近 3 轮对话的原始 Token，确保即时指令的精确执行。
* **摘要链 (Summary Chain)**：对长尾历史进行语义压缩，提取关键实体注入 System Prompt，将 Token 消耗控制在常数级别。


* **结构化注入**：利用 LangChain 的 `MessagesPlaceholder` 实现 System/Human/AI 消息的结构化隔离，防止指令注入攻击和角色混淆。

### 2.3 智能体工作流 (Agentic Workflow with LangGraph)

系统采用 **LangGraph** 将复杂的业务逻辑重构为有向循环图 (StateGraph)，实现了更高级的控制流：

* **状态机架构 (State Machine)**：明确定义了 `Supervisor` -> `Research` -> `Modify` -> `Evaluation` 的状态流转路径。
* **自我修正循环 (Self-Correction Loop)**：
    * 引入 `Evaluation Node` 对生成结果进行自动化质检。
    * 若未通过质检，工作流自动回退至 `Modify Node`，并注入专家反馈意见，强制 Agent 进行反思 (Reflection) 和重试。
* **状态持久化 (Checkpointing)**：利用 `MemorySaver` 实现状态的实时保存与恢复，支持长会话管理和断点续传。

## 3. 系统评测 (Evaluation & Benchmark)

基于 50+ 真实业务场景构建自动化评测集，采用 **LLM-as-a-Judge** 范式进行量化评估。

### 3.1 业务指标

| Metric | Baseline (Zero-shot) | CECraft | Improvement |
| --- | --- | --- | --- |
| **STAR Compliance** | 35.0% | **91.8%** | +162.5% |
| **Resume Quality Score** | 57.5 | **85.0** | +27.5 |

### 3.2 工程指标

* **Context Recall (召回率)**: 0.75
* **Faithfulness (忠实度)**: 0.90 (基于 RAGAS 框架评估)
* **End-to-End Latency**: 5.50s (P90)
* **Intent Accuracy**: 100%

## 4. 项目结构

```text
CECraft/
├── backend/                    # Python Backend (FastAPI + LangChain)
│   ├── app/
│   │   ├── services/
│   │   │   ├── graph_workflow.py # LangGraph State Machine & Workflow definition
│   │   │   ├── agent_workflow.py # LLM Services & Prompt Templates
│   │   │   └── tools/            # RAG & Web Search Tools implementation
│   │   └── ...
│   ├── crawl_docs.py           # Data crawler for Resumes/JDs
│   ├── ingest_rag.py           # Vector embedding pipeline
│   └── docker-compose.yml      # Infrastructure (Milvus, MinIO, Etcd)
├── frontend/                   # Frontend Monorepo
│   ├── packages/
│   │   ├── core/               # Custom Canvas rendering engine
│   │   ├── delta/              # Operational Transformation data structure
│   │   └── react/              # React UI components
│   └── ...
└── run.sh                      # Startup script

```

## 5. 快速开始

### 前置要求

* **Runtime**: Python 3.10+, Node.js (pnpm)
* **Infrastructure**: Docker & Docker Compose (Milvus 向量库依赖)

### 部署步骤

1. **启动基础设施**
```bash
cd backend
docker-compose up -d

```


2. **构建索引 (可选)**
如需启用 RAG 功能，需执行数据爬取与向量化入库：
```bash
python crawl_docs.py
python ingest_rag.py --source ./data/resumes_crawled --collection docs_md

```


3. **启动服务**
执行根目录启动脚本：
```bash
./run.sh

```


* Frontend: `http://localhost:8080`
* API Documentation: `http://localhost:8000/docs`