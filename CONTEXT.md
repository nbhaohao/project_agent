# Project Context

> 把这个文件给任何 AI 助手读，它就能快速理解这个项目的背景、目标和当前状态。
> 最后更新：2026-06-03（M10 完成）

---

## 关于我（开发者）

- **经验**：3 年以上后端开发，有 LLM API 实战经验
- **目标岗位**：**Agent 平台 / Runtime 工程师**（中国市场）
  - 重心 = 造 agent 跑起来的引擎本身（执行循环、上下文工程、工具沙箱、记忆/RAG、多 agent 编排、eval）
  - 不是 agent 应用层（串 prompt/工具），也不是纯后端基建
  - 定位：harness 内核 + 生产后端基建合体——"能造 agent 平台，不只是用 agent"
- **前置学习**：已完成 s01–s20 Agent harness 课程（my-agent 全绿），理解 agent loop / tool dispatch / compaction / memory 内核
- **技术背景**：Python、FastAPI、async/await、LLM API 可直接展开，不需要解释基础概念

## 这个项目是什么

**`project_agent`** —— 生产级 Agent 平台 / Runtime，求职作品。

**产品形态**：提交任务 → agent 异步执行循环（LLM↔工具）→ 流式步骤输出 → 可中断/取消 → 状态持久化 → 上下文工程 → 记忆/RAG → 多 agent 编排 → eval。

**卖点**：不是 LangChain 串流程的 agent 应用，而是造 agent 能跑起来的引擎本身，对应 Dify/Coze 背后那层 runtime。

**技术栈**：Python 3.11 / FastAPI / SQLAlchemy + Alembic / Redis / pgvector / SSE / Anthropic SDK（接 DeepSeek）/ Docker / uv

## 架构：DDD-lite 四层

```
app/
  domain/           纯业务模型与规则（Run 状态机、InvalidTransition），零框架依赖
  application/      用例编排（RunService、AgentLoop），依赖 domain + ports
    agent/          agent 执行循环 + 工具
  infrastructure/   真基建实现（Postgres/Redis/LLM 适配器），实现 application 的 ports
  interface/api/    FastAPI 路由、DTO、依赖注入
```

**原则**：依赖方向严格单向（interface→application→domain），infrastructure 实现 application 的 Protocol ports。不上全套战术 DDD（无 Aggregate/VO/Domain Event）。

## 路线图与当前进度

| 里程碑 | 状态 | 核心内容 |
|--------|------|---------|
| M0 脚手架 | ✅ 完成 | docker-compose(pg16/redis7) + FastAPI + DDD-lite 四层 + /health 探针 |
| M1 Run 模型 | ✅ 完成 | PostgreSQL + Alembic + 端口/适配器 + 提交/查询接口（uuid7 主键） |
| M2 异步执行管道 | ✅ 完成 | 独立 worker 进程 + Redis List(BRPOP) + Run 状态机推进 + 落库 |
| M3 真 agent loop | ✅ 完成 | LLM port + AsyncAnthropic 适配器 + AgentLoop + get_current_time 工具 + result/error 持久化 |
| M4 工具系统 | ✅ 完成 | Tool dataclass + ToolRegistry(capability 过滤+超时) + http_fetch/file_read + 路径穿越防护 |
| M5 SSE 流式 + 前端 | ✅ 完成 | run_messages 表 + on_message 回调 + Redis Pub/Sub + SSE 端点 + vanilla 前端 |
| M6 中断/取消 | ✅ 完成 | CancelSignal port + RedisCancelSignal + 协作式取消(loop 每轮检查) + watchdog Task + POST /runs/{id}/cancel + 前端取消按钮 |
| M7 上下文工程 | ✅ 完成 | context 管理、compaction（保头保尾）、消息历史截断 |
| M8 记忆 + RAG | ✅ 完成 | pgvector + SiliconFlow bge-m3 + remember/recall 工具 + 跨 run 语义检索 |
| **M9 多 agent 编排** | ✅ 完成 | agent-as-tool 模式 + SubAgentDefinition + researcher/summarizer 专家 + 递归深度=1 |
| **M10 eval + 可观测** | ✅ 完成 | MeteredLLMClient + Usage/RunMetrics + trace_id contextvar + JSON 日志 + metrics 落库 + SSE usage 事件 + eval harness(6 cases) + 报告 CLI |
| M11 部署收口 | 待做 | Docker 化部署 + UI 打磨 |

## 关键架构决策（已拍板，不要再提议更改）

1. **Run = 一次 agent 执行**（不是 session/conversation，session 是多个 run 的聚合，等有真需求再建）
2. **主键 uuid7**（时间有序，B-tree 友好；不用自增 bigserial 避免泄露业务量）
3. **Redis List + BRPOP**（M2/M3 够用，有意设计成"先踩 List 的坑、M6 再升级 Streams"，git history 记录这段演进）
4. **LLM port duck-typed**（`LLMClient.complete()` 返回 `Any`，结构上匹配 Anthropic Message；不做全 provider 映射，YAGNI 直到第二个 provider）
5. **前端 M5 进场**，形态 = 亮点演示台（highlight reel），vanilla HTML+JS，FastAPI 直接 serve 静态，零构建
6. **消息(messages) ≠ 记忆(memory)**：messages 是单次 run 内的工作上下文（M5 建表）；memory 是跨 run 的长期知识（M8 pgvector）
7. **工具沙箱轻量层**：capability 声明（`network`/`fs_read`）+ `asyncio.wait_for` 超时 + 路径穿越防护；进程/容器隔离留到真正需要执行任意代码时（YAGNI）

## 项目文件结构（当前 M10）

```
project_agent/
├── app/
│   ├── config.py                    # pydantic-settings，读 .env
│   ├── main.py                      # FastAPI app factory
│   ├── worker.py                    # 独立 worker 进程 entrypoint
│   ├── domain/
│   │   ├── ids.py                   # UUIDv7 生成（手写，stdlib 3.14 才有）
│   │   └── run.py                   # Run dataclass + RunStatus 枚举 + 状态机方法 + RunCancelled
│   ├── application/
│   │   ├── ports.py                 # RunRepository / RunQueue / LLMClient / MessageRepository / CancelSignal Protocol
│   │   ├── run_service.py           # submit / get / list 用例 + cancel_run()
│   │   └── agent/
│   │       ├── loop.py              # AgentLoop（接 ToolRegistry + on_message + should_cancel 回调 + compaction）
│   │       ├── events.py            # derive_events(RunMessage) → SSE 事件 dict 列表
│   │       ├── compaction.py        # estimate_tokens + compact_messages（保头保尾策略）
│   │       ├── subagent.py          # SubAgentDefinition + build_subagent_tool()（机制层）
│   │       ├── specialists.py       # RESEARCHER/SUMMARIZER + build_subagent_tools()（策略层）
│   │       └── tools/
│   │           ├── memory.py        # build_memory_tools(embedder, repo) → remember/recall Tool
│   │           ├── base.py          # Tool dataclass + ToolRegistry(capability 过滤+asyncio 超时)
│   │           └── builtin.py       # get_current_time / http_fetch / file_read + build_registry()
│   ├── domain/
│   │   ├── ids.py                   # UUIDv7 生成
│   │   ├── run.py                   # Run dataclass + RunStatus + 状态机 + record_metrics()
│   │   ├── message.py               # RunMessage dataclass
│   │   ├── memory.py                # Memory dataclass
│   │   └── usage.py                 # Usage + RunMetrics + compute_cost()（定价表，纯函数）
│   ├── infrastructure/
│   │   ├── db.py                    # async SQLAlchemy engine + SessionLocal
│   │   ├── models.py                # RunORM + RunMessageORM + MemoryORM（Vector 1024）
│   │   ├── repositories.py          # SqlAlchemyRunRepository + MessageRepository + MemoryRepository
│   │   ├── embedder.py              # SiliconFlowEmbedder（httpx, OpenAI-兼容 /embeddings）
│   │   ├── queue.py                 # RedisRunQueue（LPUSH/BRPOP）
│   │   ├── event_bus.py             # RedisEventBus（PUBLISH 到 run:{id}:events channel）
│   │   ├── cancel.py                # RedisCancelSignal（SET run:{id}:cancel / EXISTS）
│   │   ├── redis.py                 # 共享 redis.asyncio 客户端（含 pubsub_redis socket_timeout=None）
│   │   └── llm.py                   # AnthropicLLMClient + MeteredLLMClient（usage 累加装饰器）
│   ├── observability/
│   │   └── tracing.py               # trace_id ContextVar + bind_trace() + TraceFilter + JsonFormatter
│   ├── interface/api/
│   │   ├── health.py                # GET /health（liveness）GET /health/ready（readiness）
│   │   ├── runs.py                  # POST /runs, GET /runs/{id}, GET /runs, GET /runs/{id}/events, POST /runs/{id}/cancel
│   │   └── deps.py                  # FastAPI 依赖注入（session / RunService / CancelSignal 组装）
│   └── static/
│       └── index.html               # vanilla 前端（亮色）：提交框 + 3 preset + Cancel 按钮 + EventSource 渲染
├── migrations/                      # Alembic 迁移（async env）
├── tests/                           # 75 个单测（domain/service/loop/worker/compaction/memory/subagent，无 DB/LLM 依赖）
├── eval/
│   ├── dataset.json                 # 6 个 eval case（time/fetch/file/remember/recall/subagent）
│   ├── harness.py                   # async 跑 case + 断言(contains/tool_called) + 收集 metrics
│   └── __main__.py                  # CLI 入口：python -m eval，打印 ASCII 表 + SUMMARY，exit 0/1
├── scripts/
│   ├── e2e_m1.sh                    # M1 集成测试（curl 断言）
│   ├── e2e_m2.sh                    # M2 集成测试（worker stub 全链路）
│   ├── e2e_m3.sh                    # M3 集成测试（真 LLM tool-use 全链路）
│   ├── e2e_m4.sh                    # M4 集成测试（get_current_time + http_fetch + file_read）
│   ├── e2e_m5.sh                    # M5 集成测试（SSE 历史补发 + 事件类型验证 + 前端可访问）
│   ├── e2e_m6.sh                    # M6 集成测试（QUEUED 取消 + cancelled SSE 事件 + 404）
│   ├── e2e_m7.sh                    # （无独立 e2e，compaction 通过单测 + M8 e2e 隐式验证）
│   ├── e2e_m8.sh                    # M8 集成测试（remember→recall 跨 run RAG 链路验证）
│   ├── e2e_m9.sh                    # M9 集成测试（主 agent 委托 researcher sub-agent 全链路）
│   └── e2e_m10.sh                   # M10 集成测试（metrics 落库 + SSE 携带 + eval CLI 启动）
├── docker-compose.yml               # postgres:16 + redis:7
├── pyproject.toml                   # 依赖（fastapi/uvicorn/sqlalchemy/alembic/redis/anthropic）
└── .env.example                     # 环境变量模板（DATABASE_URL/REDIS_URL/LLM 三键）
```

## 与 AI 助手协作的约定

如果你是接手这个项目的 AI 助手，请遵守：

1. **YAGNI**：用不上的东西现在不创建。字段、方法、抽象都只在真正被调用时才加。
2. **小 commit**：改动文件 > 5 个时，按逻辑边界拆多个 commit，方便我 review。
3. **模块收尾仪式**：每个里程碑完成后 → 出集成测试脚本（`scripts/e2e_mX.sh`）让我手动跑 → 再出口试题检验我是否真懂。
4. **架构决策走 Opus，写代码走 Sonnet**：我用 Claude Code，`/model` 切换。遇到架构岔路口提醒我切 Opus，定完切回 Sonnet。
5. **分层不能混**：`application/` 不能 import `infrastructure/` 的具体类，只能依赖 `ports.py` 的 Protocol。
6. **不要提前加 Session 实体、run_messages 表、compaction、memory 等**——这些各有对应里程碑（M5/M7/M8）。

## 本地开发快速启动

```bash
# 1. 启动基础设施
docker compose up -d
uv run alembic upgrade head

# 2. 填写 .env（从 .env.example 复制，补 LLM 三键）
cp .env.example .env

# 3. 跑单测（无需 docker）
uv run pytest

# 4. 启动 API（终端 A）
uv run uvicorn app.main:app --reload

# 5. 启动 worker（终端 B）
uv run python -m app.worker

# 6. 验证（终端 C）
./scripts/e2e_m5.sh

# 7. 前端
open http://localhost:8000
```

API 文档：http://localhost:8000/docs
