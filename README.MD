# CECraft: Intelligent Resume Optimization System

**CECraft** 是一个集成了大语言模型（LLM）智能体与高性能富文本编辑器的简历优化平台。该系统旨在通过 Agentic Workflow（智能体工作流）解决非结构化简历数据与结构化岗位描述（JD）之间的语义匹配问题，利用 RAG（检索增强生成）技术实现简历内容的专业化重构、翻译与实时润色。

## 1. 系统概览

CECraft 采用前后端分离架构，前端基于 Canvas 引擎实现高性能渲染，后端基于 **LangGraph** 与 FastAPI 构建多智能体编排系统。

### 1.1 核心功能

* **多模态调研与咨询 (Deep Research)**：集成 Web Search 工具，支持针对薪资范围、面试题库及企业背景的外部信息检索。
    * **搜索引擎**：DuckDuckGo (隐私保护，无追踪)。
    * **网页解析**：Jina Reader (云端解析，将网页转为 LLM 友好的 Markdown)。
* **岗位匹配与优化 (Targeted Optimization)**：解析目标岗位 JD，自动提取关键技能实体，调整简历的语义侧重以提升人岗匹配度。
* **基于 STAR 法则的重写 (Structure Transformation)**：自动将描述性文本重构为符合 "Situation-Task-Action-Result" 标准的专业履历。
* **专业级富文本编辑 (Canvas Editor)**：支持 Delta 数据结构、自定义插件系统及精确的打印布局控制。

### 1.2 智能体工作流 (Agentic Workflow)

系统采用基于 LangGraph 的多智能体协作模式，实现了更细粒度的意图识别与自我修正机制：

* **总控大脑 (Supervisor)**：基于对话摘要与当前指令，将用户意图细分为 6 类：
    * `research_consult`: 纯咨询（薪资、行情）。
    * `research_modify`: 基于调研的修改（结合 JD、STAR 法则）。
    * `modify`: 纯文本润色/翻译。
    * `research_create`: 基于调研的从头撰写（针对空白内容）。
    * `create`: 纯文本撰写。
    * `chat`: 通用对话。
* **智能调研 (Researcher)**：内置 **ToolRouter**，智能选择信息源：
    * **Web Search**: 获取实时外部信息（JD、公司背景）。
    * **RAG (VectorDB)**: 检索内部方法论（简历模板、写作技巧）。
    * **Hybrid**: 双源融合，同时获取市场数据与专业话术。
* **生成与优化 (Generator)**：
    * **Context-Aware**: 结合调研结果与用户原有内容（Delta 格式）进行生成。
    * **Strict Formatting**: 强制 Markdown 输出，自动加粗关键技能，严格保留排版空格。
* **质量评估闭环 (Evaluator)**：
    * **Self-Correction**: 对生成结果进行自动化评分（意图一致性、幻觉检测、格式校验）。
    * **Retry Mechanism**: 若评分未通过，自动携带反馈意见触发重试，确保最终交付质量。
* **格式化输出 (Formatter)**：确保最终响应符合标准 API 格式。

## 2. 核心业务设计

### 2.1 用户认证与安全 (Authentication & Security)

系统采用标准的 OAuth2 密码模式与 JWT (JSON Web Token) 机制，确保用户身份验证的安全性和无状态性。

* **注册与登录流程**：
    * 用户提交注册信息后，后端通过 `bcrypt` 算法对密码进行加盐哈希存储，杜绝明文密码泄露风险。
    * 登录成功后，系统签发包含用户 ID 和过期时间的 `access_token` (JWT)。
    * 前端将 Token 存储于本地，并在后续所有 API 请求的 Header 中携带 `Authorization: Bearer <token>` 进行身份校验。
* **依赖注入**：利用 FastAPI 的 `Depends` 机制，在 API 路由层统一拦截并解析 Token，自动注入当前用户对象 (`current_user`)，实现细粒度的权限控制。

### 2.2 简历管理 (Resume Management)

简历数据的全生命周期管理，涵盖创建、编辑、存储与版本控制。

* **在线编辑与创建**：
    * 支持基于 Canvas 的高性能富文本编辑器，提供流畅的简历编写体验。
    * 支持从零创建简历或基于模板进行编辑。
* **结构化存储**：
    * 简历元数据（标题、创建时间）存储于关系型数据库。
    * 简历正文内容（Delta JSON）作为大字段存储，支持高效的读写操作。
* **版本管理**：支持对同一份简历的多次修改保存，方便用户回溯历史版本。

### 2.3 数据库设计 (Database Schema)

采用 MySQL 作为主数据库，通过 SQLAlchemy ORM 进行模型定义与操作，确保数据的一致性与完整性。

* **User 表**：存储用户基础信息。
    * `id`: 主键
    * `email`: 唯一索引，用于登录
    * `hashed_password`: 加密后的密码
    * `is_active`: 账户状态
* **Resume 表**：存储简历数据，与 User 表建立一对多关联。
    * `id`: 主键
    * `title`: 简历标题
    * `content`: 简历内容 (JSON 格式的大文本，存储 Delta 数据)
    * `user_id`: 外键，关联 User 表
    * `created_at` / `updated_at`: 时间戳

## 3. 技术架构深度解析

本项目重点解决了通用 LLM 在长上下文管理、领域知识检索及指令遵循稳定性方面的工程挑战。

### 3.1 检索增强生成 (Advanced RAG Pipeline)

为提升领域知识的召回精度，系统实现了全链路优化的 RAG 流水线：

* **两阶段检索 (Two-stage Retrieval)**：
* **召回层 (Retrieval)**：结合查询扩展 (Query Expansion) 生成多路子查询，通过高维向量检索 (Dense Retrieval) 提升 Recall。
* **排序层 (Rerank)**：引入 **GTE-Rerank** (Cross-Encoder) 模型对向量召回结果进行语义精排，显著提升 Top-K 准确率。


* **结构化索引 (Structure-aware Indexing)**：
* **AST 切分**：基于 Markdown 抽象语法树解析文档，避免暴力切分导致的语义断裂。
* **父子索引 (Parent-Child Indexing)**：采用 "Small-to-Big" 策略，检索细粒度切片（Child Chunk）并映射回上下文完整的父文档（Parent Document），平衡检索粒度与生成质量。


* **动态检索 (Adaptive Retrieval)**：
* Supervisor 模块内置查询重写 (Query Rewriting) 逻辑，将用户自然语言转化为高信噪比的搜索关键词。



### 3.2 智能联网搜索 (Intelligent Web Search)

针对通用大模型知识滞后的问题，系统构建了基于 **Search-Crawl-Summarize** 范式的实时信息获取引擎：

* **查询意图优化 (Query Refinement)**：
    * 利用 LLM 将用户模糊的自然语言（如“帮我查下现在的行情”）转化为高信噪比的搜索关键词（如“2024 前端开发 薪资范围 北京”），显著提升搜索命中率。
* **策略性搜索 (Strategic Search)**：
    * **多源支持**：默认集成 **DuckDuckGo** (隐私保护)，可选接入 **Bocha** (专业搜索 API)。
    * **智能过滤 (Domain Filtering)**：内置白名单机制，优先召回技术社区 (GitHub, StackOverflow, Juejin) 与官方招聘页，自动降权 SEO 农场与视频站点。
* **高并发网页解析 (Concurrent Parsing)**：
    * **Jina Reader 集成**：利用 `r.jina.ai` 服务将异构 HTML 实时转换为 LLM 友好的 Markdown 格式，保留核心语义结构。
    * **异步并发**：基于 `aiohttp` 实现多路并行抓取，将平均响应时间控制在秒级。
* **抗噪摘要生成 (Anti-Noise Summarization)**：
    * 设计专用的 Prompt 模板，强制模型执行“去噪”操作，剔除广告与无关导航，精准提取 JD 中的硬性技能与岗位职责。

### 3.3 无状态上下文管理 (Stateless Context Management)

采用“前端托管 + 混合记忆”架构，解决服务端会话状态存储压力及 Token 上下文窗口限制：

* **RESTful 架构**：后端完全无状态，会话历史由客户端维护并按需注入，支持服务水平的线性扩展。
* **混合压缩策略 (Hybrid Memory)**：
* **滑动窗口 (Sliding Window)**：保留最近 3 轮对话的原始 Token，确保即时指令的精确执行。
* **摘要链 (Summary Chain)**：对长尾历史进行语义压缩，提取关键实体注入 System Prompt，将 Token 消耗控制在常数级别。


* **结构化注入**：利用 LangChain 的 `MessagesPlaceholder` 实现 System/Human/AI 消息的结构化隔离，防止指令注入攻击和角色混淆。

### 3.4 智能体工作流 (Agentic Workflow with LangGraph)

系统采用 **LangGraph** 将复杂的业务逻辑重构为有向循环图 (StateGraph)，实现了更高级的控制流：

* **状态机架构 (State Machine)**：明确定义了 `Supervisor` -> `Research` -> `Modify` -> `Evaluation` 的状态流转路径。
* **双向格式桥接 (Bi-directional Format Bridge)**：
    * **Delta to Markdown**: 将前端复杂的富文本数据结构（Delta）无损转换为 LLM 可理解的 Markdown 格式，保留加粗、列表、链接等核心语义。
    * **Markdown to Delta**: 自研解析引擎，将 LLM 生成的 Markdown 文本自动映射回 Canvas 渲染所需的 Delta 数据结构，支持多级列表、样式嵌套及 Slate 兼容格式 (Origin Data) 的同步生成。
* **自我修正循环 (Self-Correction Loop)**：
    * 引入 `Evaluation Node` 对生成结果进行自动化质检。
    * 若未通过质检，工作流自动回退至 `Modify Node`，并注入专家反馈意见，强制 Agent 进行反思 (Reflection) 和重试。
* **状态持久化 (Checkpointing)**：利用 `MemorySaver` 实现状态的实时保存与恢复，支持长会话管理和断点续传。

### 3.5 高性能渲染引擎 (High-Performance Rendering Engine)

前端摒弃了传统的 DOM 编辑方案，采用自研 Canvas 引擎实现像素级渲染控制：

* **Custom Canvas Engine**: 基于 `CanvasRenderingContext2D` 的直接绘制，支持 60FPS 流畅渲染与 `devicePixelRatio` 高清屏适配。
* **Spatial Delta Model**: 采用 `x, y, z, width, height` 的空间数据模型替代线性 OT 算法，原生支持复杂的自由布局与组件嵌套。
* **Plugin Architecture**: 采用微内核+插件架构，Text、Image、Rect 等均为独立插件，具备极高的扩展性。
* **Core Modules**: 内置完整的 History (Undo/Redo)、Selection (多选/框选) 及 Clipboard (剪贴板) 模块，提供桌面级的编辑体验。

## 5. 系统评测 (Evaluation & Benchmark)

基于 50+ 真实业务场景构建自动化评测集，采用 **LLM-as-a-Judge** 范式进行量化评估。

### 5.1 业务指标

| Metric | Baseline (Zero-shot) | CECraft | Improvement |
| --- | --- | --- | --- |
| **STAR Compliance** | 35.0% | **91.8%** | +162.5% |
| **Resume Quality Score** | 57.5 | **85.0** | +27.5 |

### 5.2 工程指标

* **Context Recall (召回率)**: 0.75
* **Faithfulness (忠实度)**: 0.90 (基于 RAGAS 框架评估)
* **End-to-End Latency**: 5.50s (P90)
* **Intent Accuracy**: 100%

## 6. 项目结构

```text
CECraft/
├── backend/                    # Python Backend (FastAPI + LangChain)
│   ├── app/
│   │   ├── api/              # RESTful API Endpoints (Auth, Resume, Agent)
│   │   ├── core/             # Config & Security (JWT, Password Hashing)
│   │   ├── db/               # Database Session & Base Models
│   │   ├── models/           # SQLAlchemy ORM Models (User, Resume)
│   │   ├── schemas/          # Pydantic Schemas (Request/Response Validation)
│   │   ├── services/
│   │   │   ├── graph_workflow.py # LangGraph State Machine & Workflow definition
│   │   │   ├── agent_workflow.py # LLM Services & Prompt Templates
│   │   │   └── tools/            # RAG & Web Search Tools implementation
│   │   └── ...
│   ├── crawl_docs.py           # Data crawler for Resumes/JDs
│   ├── ingest_rag.py           # Vector embedding pipeline
│   └── docker-compose.yml      # Infrastructure (Milvus, MinIO, Etcd, MySQL)
├── frontend/                   # Frontend Monorepo
│   ├── packages/
│   │   ├── core/               # Custom Canvas rendering engine
│   │   ├── delta/              # Operational Transformation data structure
│   │   └── react/              # React UI components
│   └── ...
└── run.sh                      # Startup script

```

## 7. 快速开始

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