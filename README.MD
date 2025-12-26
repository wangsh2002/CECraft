# CECraft - 智能简历优化系统

CECraft 是一个集成了 AI 智能体的现代化简历编辑器。它结合了强大的富文本编辑能力（Frontend）和基于大语言模型的智能代理（Backend），能够帮助用户调研岗位要求、咨询简历建议，并自动优化和润色简历内容。

## 核心功能

*   **智能简历诊断与优化**：
    *   **调研咨询 (Research Consult)**：查询薪资范围、面试题、公司背景等外部信息。
    *   **调研修改 (Research Modify)**：根据搜索到的岗位 JD 或行业标准，针对性地优化简历技能和经历。
    *   **直接修改 (Modify)**：对简历内容进行润色、精简、翻译或纠错。
    *   **闲聊 (Chat)**：提供通用的简历建议和指导。
*   **专业级富文本编辑器**：
    *   基于 Canvas 的高性能渲染引擎。
    *   支持富文本数据结构 (Delta)。
    *   模块化插件系统。
*   **RAG (检索增强生成) - 深度优化版**：
    *   **Two-stage Retrieval (两阶段检索)**：
        *   **Query Expansion (查询扩展)**：利用 LLM 生成多路子查询，提升召回覆盖率 (Recall)。
        *   **Rerank (重排序)**：引入 Cross-Encoder 模型对向量召回结果进行精排，大幅提升 Top-K 准确率。
    *   **Advanced Indexing (高级索引策略)**：
        *   **Structure-aware Chunking (结构化切分)**：基于 Markdown AST 解析文档结构，确保知识片段的语义完整性。
        *   **Parent-Child Indexing (父子索引)**：Small-to-Big 策略，检索细粒度子块，返回粗粒度父文档，兼顾检索精度与上下文完整性。
    *   **Evaluation (自动化评估)**：内置 RAG 评估流水线，量化 Context Recall 和 Answer Faithfulness 指标。

## 模块说明

### Backend (后端)

后端基于 **FastAPI** 和 **LangChain** 构建，负责处理 AI 逻辑、数据检索和 API 服务。

*   **Agent Workflow**: 采用 Supervisor 架构，将用户意图分类为 `research_consult`, `research_modify`, `modify`, `chat` 四类，并调度相应的工具。
*   **RAG System**: 使用 Milvus 作为向量数据库，存储爬取的行业数据，为 Agent 提供上下文支持。
*   **Tools**: 集成了 Web Search (联网搜索) 和 RAG Retriever (本地知识库检索) 工具。

### Frontend (前端)

前端采用 **React** + **Rspack** 的 Monorepo 架构，核心是一个自研的富文本/图形编辑器引擎。

*   **Core**: 编辑器的核心引擎，处理画布渲染、事件分发、历史记录管理等。
*   **Delta**: 定义了文档的数据结构，用于描述富文本内容。
*   **Plugin**: 插件系统，允许扩展编辑器功能。
*   **React**: UI 层，使用 Arco Design 组件库，提供用户交互界面。

## 项目结构与文件说明

```text
CECraft/
├── README.MD                   # 项目说明文档
├── run.sh                      # 一键启动脚本 (同时启动前后端)
├── technical_report.md         # 技术报告
├── backend/                    # 后端代码目录
│   ├── main.py                 # FastAPI 应用入口
│   ├── crawl_docs.py           # 数据爬虫脚本，用于抓取简历范文和岗位 JD
│   ├── ingest_rag.py           # RAG 数据入库脚本，将 Markdown 文档存入 Milvus
│   ├── docker-compose.yml      # 基础设施编排 (Milvus, MinIO, Etcd)
│   ├── requirements.txt        # Python 依赖列表
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       └── agent.py    # Agent 相关 API 路由
│   │   ├── core/
│   │   │   └── config.py       # 项目配置 (环境变量等)
│   │   ├── schemas/
│   │   │   └── agent.py        # Pydantic 数据模型定义
│   │   └── services/
│   │       ├── agent_workflow.py # LangChain Agent 核心工作流逻辑 (Supervisor & Tools)
│   │       └── tools/
│   │           ├── rag_retriever.py # RAG 检索工具
│   │           └── web_search.py    # 联网搜索工具
│   ├── data/                   # 数据存储目录
│   │   ├── STAR法则.md          # 内置参考文档
│   │   └── resumes_crawled/    # 爬虫抓取的简历和 JD 数据
│   ├── tests/                  # 测试代码
│   └── volumes/                # Docker 挂载卷 (Milvus 数据持久化)
└── frontend/                   # 前端代码目录 (Monorepo)
    ├── package.json            # 根依赖配置
    ├── pnpm-workspace.yaml     # pnpm workspace 配置
    ├── packages/
    │   ├── core/               # 编辑器核心引擎包
    │   │   └── src/
    │   │       ├── canvas/     # 画布渲染逻辑
    │   │       ├── editor/     # 编辑器主控逻辑
    │   │       ├── event/      # 事件系统
    │   │       └── history/    # 撤销/重做历史记录
    │   ├── delta/              # 数据结构包 (类似 Quill Delta)
    │   ├── plugin/             # 编辑器插件系统
    │   ├── react/              # React UI 应用包 (主应用)
    │   │   ├── rspack.config.js # Rspack 构建配置
    │   │   └── src/            # 前端页面源码
    │   └── utils/              # 通用工具函数包
    └── ...
```

## 快速开始

### 环境要求

*   Node.js & pnpm
*   Python 3.10+
*   Docker & Docker Compose (用于运行 Milvus)

### 1. 启动基础设施

首先启动向量数据库 Milvus 和对象存储 MinIO：

```bash
cd backend
docker-compose up -d
```

### 2. 数据准备 (可选)

如果你需要使用 RAG 功能，可以先爬取数据并入库：

```bash
# 爬取数据
python crawl_docs.py

# 数据入库 (需确保 Docker 服务已启动)
python ingest_rag.py --source ./data/resumes_crawled --collection docs_md
```

### 3. 启动服务

你可以使用根目录下的脚本同时启动前后端：

```bash
./run.sh
```

或者分别启动：

**Backend:**

```bash
cd backend
pip install -r requirements.txt
python main.py
```

**Frontend:**

```bash
cd frontend
pnpm install
pnpm dev
```

访问前端地址通常为: `http://localhost:8080` (具体视控制台输出而定)。
API 文档地址: `http://localhost:8000/docs`。
