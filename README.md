# project_agent

生产级 **Agent 平台 / Runtime** —— 求职作品。

造 agent 跑起来的引擎本身:提交任务 → agent 异步执行循环(LLM↔工具) → 流式步骤 →
可中断/取消 → 状态持久化 → 上下文工程 → 记忆/RAG → 多 agent 编排 → eval。
FastAPI + PG + Redis 作底座。

## 架构(DDD-lite 四层)

```
app/
  domain/          纯业务模型与规则(Task 状态机),不依赖框架
  application/     用例编排(提交/取消任务…),调 domain + infra 端口
  infrastructure/  真基建实现:Postgres / Redis / LLM client
  interface/api/   FastAPI 路由、DTO、依赖注入
```

## 快速启动(M11 一键全栈)

前置:Docker daemon 运行中、`.env` 已配置。

```bash
# 1. 配置密钥(首次)
cp .env.example .env   # 填入 ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL / MODEL_ID / EMBEDDING_API_KEY

# 2. 一键起全栈(postgres + redis + 迁移 + api + worker)
docker compose up -d

# 3. 验证
curl localhost:8000/health/ready   # {"status":"ok","checks":{"postgres":"ok","redis":"ok"}}
open http://localhost:8000         # 前端 demo
```

停:`docker compose down`(加 `-v` 清数据卷)。
源码变更后重建镜像:`docker compose build && docker compose up -d`。

## 本地开发模式(uv)

前置:Docker daemon + `uv` 已装。

```bash
cp .env.example .env
docker compose up -d postgres redis   # 只起基建
uv sync
uv run alembic upgrade head
uv run pytest                          # 97 个单测应全绿
uv run uvicorn app.main:app --reload   # 终端 A
uv run python -m app.worker            # 终端 B
curl localhost:8000/health/ready       # 验证
# Swagger UI: http://localhost:8000/docs
```

## 路线图(Agent 平台/Runtime)

- **M0 脚手架** ✅ docker-compose(pg/redis) + FastAPI + DDD-lite 四层 + health 探针
- **M1 Run 模型** ✅ PostgreSQL + Alembic + 端口/适配器 + 提交/查询接口(uuid7 主键)
- **M2 异步执行管道** ✅ 独立 worker 进程 + Redis List(BRPOP) + Run 状态机
- **M3 真 agent loop** ✅ LLM port + AsyncAnthropic 适配器 + AgentLoop + 工具调用
- **M4 工具系统** ✅ Tool dataclass + ToolRegistry(capability 过滤+超时) + http_fetch/file_read
- **M5 SSE 流式 + 前端** ✅ run_messages 表 + Redis Pub/Sub + SSE 端点 + vanilla 前端
- **M6 中断/取消** ✅ CancelSignal port + 协作式取消 + watchdog Task + POST /runs/{id}/cancel
- **M7 上下文工程** ✅ compaction（保头保尾）+ estimate_tokens + context_limit 参数
- **M8 记忆 + RAG** ✅ pgvector + SiliconFlow bge-m3 + remember/recall 工具 + 跨 run 语义检索
- **M9 多 agent 编排** ✅ agent-as-tool 模式 + researcher/summarizer 专家 + capability 隔离 + 递归深度=1
- **M10 eval + 可观测** ✅ MeteredLLMClient + Usage/RunMetrics + trace_id contextvar + JSON 日志 + metrics 落库 + SSE usage 事件 + eval harness(6 cases) + 报告 CLI
- **M11 部署收口 + UI 打磨** ✅ Dockerfile(uv 多阶段) + docker-compose 全栈(migrate/api/worker) + trace_id 展示 + stream 滚动 + 运行状态
