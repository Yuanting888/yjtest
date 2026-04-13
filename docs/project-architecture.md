# YJTest 项目架构分析文档

> 版本：v1.4.0 | 更新时间：2026-04-08 | 作者：MGdaas Lab

---

## 一、项目总览

YJTest 是一个**企业级、全栈、AI 原生的测试自动化平台**。核心定位是：用 AI 替代/辅助测试工程师完成从需求分析、用例生成到自动化执行的全链路工作。

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────────┐
│              YJTest_Vue (前端 Vue 3 + TS)               │
│  Arco Design UI · Pinia · Vue Router · Monaco Editor    │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP REST / WebSocket
                       ▼
┌─────────────────────────────────────────────────────────┐
│           YJTest_Django (后端 Django 5.2)               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ 项目管理 │ │ 用例管理 │ │ 知识库   │ │ 需求评审 │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│  ┌─────────────────────────────────────────────────┐   │
│  │     LangGraph AI 引擎（核心）                   │   │
│  │  LLM 调用 + MCP 工具 + RAG 知识库检索           │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ UI自动化 │ │ MCP工具  │ │ 任务中心 │ │ 技能库   │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │ WebSocket
                       ▼
┌─────────────────────────────────────────────────────────┐
│         YJTest_Actuator (独立执行器 Python)             │
│              Playwright 浏览器自动化引擎                │
└─────────────────────────────────────────────────────────┘

基础设施：PostgreSQL · Redis · Qdrant · Celery · MCP服务
```

---

## 三、各模块功能详解

### 3.1 后端（YJTest_Django）— 16 个 Django App

| 模块 | 功能说明 |
|------|----------|
| `accounts` | JWT + API Key 双重认证，RBAC 权限（Owner/Admin/Member） |
| `projects` | 多项目管理，数据隔离，成员权限分配 |
| `testcases` | 用例 CRUD、模块分类、嵌套步骤、Excel 导出 |
| `langgraph_integration` | **核心 AI 引擎**，LangGraph 驱动的对话与用例生成，流式响应，Token 统计 |
| `knowledge` | 知识库管理，文档向量化（PDF/DOCX/TXT），Qdrant + BM25 混合检索，RAG |
| `mcp_tools` | MCP 工具集成（stdio/HTTP/SSE），工具调用日志，HITL 人工审批 |
| `ui_automation` | 页面/元素/步骤管理，测试用例执行，截屏，Trace 记录 |
| `requirements` | AI 需求评审，风险分析，评审报告生成 |
| `orchestrator_integration` | 复杂工作流编排，Agent Loop，任务调度 |
| `task_center` | 定时任务，Celery Beat，执行记录 |
| `skills` | 可扩展技能库，自定义工具集 |
| `prompts` | 提示词模板管理与版本控制 |
| `api_keys` | LLM 供应商密钥管理 |
| `testcase_templates` | 用例模板管理 |

### 3.2 前端（YJTest_Vue）

Vue 3 + TypeScript，Arco Design 组件库，Monaco Editor 代码编辑，Pinia 状态管理。按 `features/` 目录做功能模块化拆分，对应后端各业务模块。

### 3.3 执行器（YJTest_Actuator）

独立 Python 进程，通过 WebSocket 连接后端，接收任务后用 Playwright 驱动真实浏览器执行 UI 自动化，结果实时回传。支持打包成 EXE 分发到测试机器，支持多执行器分布式部署。

### 3.4 MCP 服务（YJTest_MCP）

独立容器，提供两类服务：

- `YJTest_tools`（端口 8914）：封装平台自身能力为 MCP 工具，供 AI Agent 调用
- `ms_mcp_api`（端口 8915）：对接外部测试平台（如 MS 测试系统）

---

## 四、核心工作流

```
用户输入需求描述
      ↓
LangGraph AI 引擎
  ├── 调用 LLM（OpenAI / Qwen 等）
  ├── 检索知识库（RAG：Qdrant 向量 + BM25）
  └── 调用 MCP 工具（获取页面信息、执行操作等）
      ↓
生成结构化测试用例（步骤 / 预期结果 / 优先级）
      ↓
用例管理（保存 / 编辑 / 导出）
      ↓
下发到执行器（WebSocket）
      ↓
Playwright 执行 → 截屏 + 结果回传
```

---

## 五、技术栈一览

| 层级 | 技术选型 |
|------|----------|
| 后端框架 | Django 5.2 + Django REST Framework |
| AI 引擎 | LangChain + LangGraph + FastMCP |
| 异步任务 | Celery + Redis |
| 前端框架 | Vue 3 + TypeScript + Vite |
| UI 组件库 | Arco Design Vue |
| 关系数据库 | PostgreSQL（生产）/ SQLite（开发） |
| 缓存/消息队列 | Redis |
| 向量数据库 | Qdrant |
| 浏览器自动化 | Playwright |
| 容器化部署 | Docker Compose，镜像托管于 GHCR |

---

## 六、部署服务端口映射

| 服务 | 容器内端口 | 宿主机端口 | 说明 |
|------|-----------|-----------|------|
| frontend | 80 | 8913 | Vue 前端（Nginx） |
| backend | 8000 | 8912 | Django API |
| postgres | 5432 | 8919 | PostgreSQL 数据库 |
| redis | 6379 | 8911 | Redis 缓存/消息队列 |
| qdrant | 6333 | 8918 | 向量数据库 |
| mcp (tools) | 8006 | 8914 | YJTest MCP 工具服务 |
| mcp (ms_api) | 8007 | 8915 | MS MCP API 服务 |
| playwright-mcp | 8931 | 8916 | Playwright MCP 服务 |
| xinference | 9997 | 8917 | 模型推理服务（可选） |

---

## 七、后续利用与优化建议

### 7.1 近期（跑通基础流程）

1. **配置 LLM 接入** — 在 `.env` 里填好 `AI_API_URL` / `AI_API_KEY` / `AI_MODEL`，这是整个平台能跑起来的前提
2. **配置嵌入服务** — 知识库功能依赖 Embedding 模型，可以用 Ollama 本地跑，或者接 OpenAI
3. **跑通完整流程** — 创建项目 → 上传文档到知识库 → AI 对话生成用例 → 执行器跑一遍

### 7.2 中期（提升质量）

- **知识库质量**：调整 `chunk_size` / `chunk_overlap`，开启 Reranker 精排，提升 RAG 召回质量
- **提示词工程**：在 `prompts` 模块里优化系统提示词，让用例生成更贴合业务场景
- **执行器扩展**：多台机器部署多个 Actuator，实现并行执行
- **技能库扩展**：在 `YJTest_Skills` 里添加自定义工具，让 AI Agent 能调用更多业务系统

### 7.3 长期（架构演进）

- 引入 Xinference 本地部署 Embedding + Reranker 模型，降低对外部 API 的依赖
- 对接 CI/CD（Jenkins / GitLab CI），让测试执行融入发布流水线
- 完善 `requirements` 模块的需求评审能力，形成需求 → 用例 → 执行的闭环
- 给 `orchestrator_integration` 加更复杂的 Agent 编排逻辑，支持多步骤自主测试

---

## 八、快速启动

```bash
# 1. 复制环境变量配置
cp .env.example .env

# 2. 填写必要配置（LLM、数据库等）
vim .env

# 3. 启动所有服务
./run_compose.sh

# 4. 访问前端
open http://localhost:8913
# 默认账号：admin / admin123456
```

---

> 核心价值：LangGraph + RAG + MCP 的组合让 AI 能真正"理解业务"来生成高质量测试用例，而不只是简单的模板填充。
