#!/usr/bin/env bash
# M6 集成测试 — 验证取消控制面:
#   1. POST /runs/{id}/cancel on QUEUED run → 202 + status=cancelled
#   2. GET /runs/{id}/events on CANCELLED run → 补历史后发 cancelled 事件关流
#   3. POST /runs/{unknown}/cancel → 404
#
# 前置(三个终端 — worker 可选,本脚本只测 QUEUED 取消无需 worker):
#   docker compose up -d && uv run alembic upgrade head
#   uv run uvicorn app.main:app          # 终端 A
# 然后:
#   ./scripts/e2e_m6.sh
set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
BODY=/tmp/e2e_m6_body.json
SSE=/tmp/e2e_m6_sse.txt
pass=0

assert_code() {
  if [ "$2" = "$1" ]; then
    echo "  ✅ $3 ($2)"
    pass=$((pass + 1))
  else
    echo "  ❌ $3 — 期望 $1 实际 $2"
    cat "$BODY"; exit 1
  fi
}

json() { python3 -c "import json,sys;print(json.load(open('$BODY'))$1)"; }

submit() {
  local code
  code=$(curl -s -o "$BODY" -w '%{http_code}' \
    -X POST "$BASE/runs" \
    -H 'Content-Type: application/json' \
    -d '{"input":"sleep forever"}')
  assert_code 201 "$code" "POST /runs" >&2
  json "['id']"
}

assert_event() {
  local pattern="$1" label="$2"
  if grep -q "$pattern" "$SSE"; then
    echo "  ✅ $label"
    pass=$((pass + 1))
  else
    echo "  ❌ $label — 未找到 pattern: $pattern"
    cat "$SSE"; exit 1
  fi
}

# ── 1. readiness ──────────────────────────────────────────────────────────────
echo "[1] readiness"
code=$(curl -s -o "$BODY" -w '%{http_code}' "$BASE/health/ready")
assert_code 200 "$code" "GET /health/ready"

# ── 2. 提交 run 后立即取消(QUEUED 路径,无需 worker) ────────────────────────
echo
echo "[2] 提交 run → 立即 cancel (QUEUED 路径)"
RID=$(submit)
pass=$((pass + 1))
echo "  run id = $RID"

code=$(curl -s -o "$BODY" -w '%{http_code}' \
  -X POST "$BASE/runs/$RID/cancel")
assert_code 202 "$code" "POST /runs/{id}/cancel"

status=$(json "['status']")
if [ "$status" = "cancelled" ]; then
  echo "  ✅ status=cancelled 已落库"
  pass=$((pass + 1))
else
  echo "  ❌ 期望 status=cancelled 实际 $status"; exit 1
fi

# ── 3. SSE 对 CANCELLED run 补历史后发 cancelled 事件 ────────────────────────
echo
echo "[3] GET /runs/{id}/events — CANCELLED run 应发 cancelled 终态事件后关流"
curl -s -N --max-time 10 "$BASE/runs/$RID/events" > "$SSE"
echo "  收到事件行数: $(wc -l < "$SSE")"

assert_event '"type": "cancelled"' "cancelled 事件存在(终态关流)"

# ── 4. 取消不存在的 run 返回 404 ─────────────────────────────────────────────
echo
echo "[4] POST /runs/{unknown}/cancel → 404"
FAKE_ID="00000000-0000-0000-0000-000000000000"
code=$(curl -s -o "$BODY" -w '%{http_code}' \
  -X POST "$BASE/runs/$FAKE_ID/cancel")
assert_code 404 "$code" "POST /runs/{unknown}/cancel"

echo
echo "🎉 M6 集成测试通过($pass 项断言) — 取消控制面验证"
