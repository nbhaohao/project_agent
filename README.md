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

## M0 跑起来

前置:Docker daemon 运行中、`uv` 已装。

```bash
# 1. 起依赖基建(Postgres + Redis)
docker compose up -d

# 2. 装依赖
uv sync

# 3. 配置(首次)
cp .env.example .env

# 4. 单元测试(无依赖,应全绿)
uv run pytest

# 5. 起服务
uv run uvicorn app.main:app --reload

# 6. E2E 验证
curl localhost:8000/health          # {"status":"ok"}
curl localhost:8000/health/ready     # postgres/redis 全 ok → 200
# Swagger UI: http://localhost:8000/docs
```

停依赖:`docker compose down`(加 `-v` 连数据卷一起删)。

## 路线图(Agent 平台/Runtime)

- **M0 脚手架** ✅ docker-compose(pg/redis) + FastAPI + DDD-lite 四层 + health 探针
- M1 Run/Session 模型 + PostgreSQL + Alembic(持久化一次 agent 执行)
- M2 Agent 执行循环进 worker(LLM↔工具核心) + Redis 队列异步下发
- M3 工具系统/工具注册表 + 沙箱化工具执行
- M4 SSE 流式(步骤/token/工具调用) + 最小前端"看 agent 跑"
- M5 中断/取消运行中的 agent
- M6 上下文工程(context 管理、compaction、消息历史)
- M7 记忆 + RAG(pgvector + embedding)
- M8 多 agent 编排(sub-agent / planner-executor / agent-as-tool)
- M9 eval + guardrails(eval harness、trace_id、成本可观测)
- M10 部署收口 + UI 打磨
