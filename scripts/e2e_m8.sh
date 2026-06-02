#!/usr/bin/env bash
# M8 集成测试 — 验证跨 run 记忆 RAG 全链路:
#   1. run A: agent 用 remember 工具存入一个唯一词
#   2. run B: agent 用 recall 工具检索并在结果中复述该词
#
# 前置(三个终端):
#   docker compose up -d && uv run alembic upgrade head
#   uv run uvicorn app.main:app          # 终端 A
#   uv run python -m app.worker          # 终端 B
# 然后:
#   ./scripts/e2e_m8.sh
#
# 需要 .env 里有:
#   ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL / MODEL_ID
#   EMBEDDING_API_KEY (SiliconFlow bge-m3, 免费注册 siliconflow.cn)
set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
BODY=/tmp/e2e_m8_body.json
pass=0

# 唯一标识词,降低 LLM 凭空猜中的概率
MAGIC="zephyr_7734"

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
  local prompt="$1"
  local code
  code=$(curl -s -o "$BODY" -w '%{http_code}' \
    -X POST "$BASE/runs" -H 'Content-Type: application/json' \
    -d "{\"input\":$(python3 -c "import json,sys;print(json.dumps(sys.argv[1]))" "$prompt")}")
  assert_code 201 "$code" "POST /runs" >&2
  json "['id']"
}

wait_terminal() {
  local rid="$1"
  for i in $(seq 1 90); do
    curl -s -o "$BODY" "$BASE/runs/$rid" > /dev/null
    local status
    status=$(json "['status']")
    echo "  t=${i}s status=$status" >&2
    if [ "$status" = "succeeded" ] || [ "$status" = "failed" ] || [ "$status" = "cancelled" ]; then
      break
    fi
    sleep 1
  done
  json "['status']"
}

# ── 1. readiness ──────────────────────────────────────────────────────────────
echo "[1] readiness"
code=$(curl -s -o "$BODY" -w '%{http_code}' "$BASE/health/ready")
assert_code 200 "$code" "GET /health/ready"

# ── 2. run A: remember ────────────────────────────────────────────────────────
echo
echo "[2] run A — agent 用 remember 工具存入 magic word: $MAGIC"
RID_A=$(submit "Use the remember tool to store exactly this text: '$MAGIC is the secret code'. Do not do anything else.")
pass=$((pass + 1))
echo "  run id = $RID_A"

status=$(wait_terminal "$RID_A")
if [ "$status" = "succeeded" ]; then
  echo "  ✅ run A succeeded"
  pass=$((pass + 1))
else
  echo "  ❌ run A 未成功: status=$status error=$(json "['error']")"
  exit 1
fi

# ── 3. run B: recall ──────────────────────────────────────────────────────────
echo
echo "[3] run B — agent 用 recall 工具检索 magic word"
RID_B=$(submit "Use the recall tool to search for 'secret code' and tell me exactly what you find.")
pass=$((pass + 1))
echo "  run id = $RID_B"

status=$(wait_terminal "$RID_B")
if [ "$status" = "succeeded" ]; then
  echo "  ✅ run B succeeded"
  pass=$((pass + 1))
else
  echo "  ❌ run B 未成功: status=$status error=$(json "['error']")"
  exit 1
fi

result=$(json "['result']")
echo "  result: $result"

if echo "$result" | grep -qi "$MAGIC"; then
  echo "  ✅ result 包含 magic word ($MAGIC) — 跨 run 记忆验证通过"
  pass=$((pass + 1))
else
  echo "  ❌ result 不含 magic word ($MAGIC) — recall 未取到记忆"
  exit 1
fi

echo
echo "🎉 M8 集成测试通过($pass 项断言) — 跨 run RAG 记忆全链路验证"
