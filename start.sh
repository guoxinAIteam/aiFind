#!/bin/bash
# 智能采集运营平台 — 一键启动脚本
set -euo pipefail
cd "$(dirname "$0")"

MODE="prod"
REBUILD_FRONTEND="0"
NO_INSTALL="0"

usage() {
  cat <<'EOF'
用法:
  ./start.sh [--mode prod|dev] [--rebuild-frontend] [--no-install]

说明:
  --mode prod           构建前端 dist（如需）+ 启动后端（默认）
  --mode dev            前后端并行启动（前端 Vite 热更新）
  --rebuild-frontend    强制重新构建前端 dist（prod 模式）
  --no-install          跳过依赖安装（pip/npm）
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --mode=*)
      MODE="${1#*=}"
      shift 1
      ;;
    --rebuild-frontend)
      REBUILD_FRONTEND="1"
      shift 1
      ;;
    --no-install)
      NO_INSTALL="1"
      shift 1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[错误] 未知参数: $1"
      echo ""
      usage
      exit 1
      ;;
  esac
done

banner() {
  echo "========================================="
  echo "  智能采集运营平台"
  echo "  Intelligent Collection Operations Platform"
  echo "========================================="
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[错误] 未找到命令: $1"
    exit 1
  fi
}

port_in_use() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  else
    return 1
  fi
}

install_python_deps_if_needed() {
  if [[ "$NO_INSTALL" == "1" ]]; then
    echo "[依赖] 跳过 Python 依赖安装（--no-install）"
    return 0
  fi

if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "[依赖] 安装 Python 依赖..."
    pip3 install -r requirements.txt -q
  else
    echo "[依赖] Python 依赖已就绪"
  fi
}

install_frontend_deps_if_needed() {
  if [[ "$NO_INSTALL" == "1" ]]; then
    echo "[依赖] 跳过前端依赖安装（--no-install）"
    return 0
  fi

  echo "[依赖] 安装前端依赖..."
  (cd frontend && npm install --silent)
}

build_frontend_if_needed() {
  if [[ "$MODE" != "prod" ]]; then
    return 0
  fi

  if [[ "$REBUILD_FRONTEND" == "1" ]]; then
    rm -rf frontend/dist
  fi

  if [ ! -d "frontend/dist" ]; then
    echo "[前端] 构建前端..."
    (cd frontend && npm run build)
  else
    echo "[前端] 前端已构建（frontend/dist 存在）"
  fi
}

start_backend() {
  if port_in_use 8000; then
    echo "[错误] 端口 8000 已被占用，请先释放后再启动。"
    exit 1
  fi

  echo "[后端] 启动中（http://localhost:8000）..."
  python3 main.py
}

start_dev() {
  need_cmd npm
  need_cmd python3

  if port_in_use 8000; then
    echo "[错误] 端口 8000 已被占用，请先释放后再启动。"
    exit 1
  fi
  if port_in_use 5173; then
    echo "[错误] 端口 5173 已被占用，请先释放后再启动。"
    exit 1
  fi

  install_python_deps_if_needed
  install_frontend_deps_if_needed

  echo "========================================="
  echo "开发模式已启动（按 Ctrl+C 一次性停止）"
  echo "  前端: http://localhost:5173"
  echo "  后端: http://localhost:8000"
  echo "  API:  http://localhost:8000/docs"
  echo "========================================="

  set +e
  python3 main.py & BACKEND_PID=$!
  (cd frontend && npm run dev) & FRONTEND_PID=$!

  cleanup() {
    echo ""
    echo "[停止] 正在关闭服务..."
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
    wait "$FRONTEND_PID" >/dev/null 2>&1 || true
    wait "$BACKEND_PID" >/dev/null 2>&1 || true
    echo "[停止] 已退出"
  }
  trap cleanup INT TERM EXIT

  wait "$BACKEND_PID"
}

banner

case "$MODE" in
  prod)
    need_cmd python3
    install_python_deps_if_needed
    need_cmd npm
    if [[ "$NO_INSTALL" != "1" ]]; then
      # prod 模式只有在需要构建时才安装依赖，减少启动时间
      if [[ "$REBUILD_FRONTEND" == "1" || ! -d "frontend/dist" ]]; then
        install_frontend_deps_if_needed
      fi
    fi
    build_frontend_if_needed

    echo "========================================="
    echo "生产/演示模式启动（按 Ctrl+C 停止）"
    echo "  访问地址: http://localhost:8000"
    echo "  API 文档: http://localhost:8000/docs"
    echo "========================================="
    echo ""
    start_backend
    ;;
  dev)
    start_dev
    ;;
  *)
    echo "[错误] --mode 仅支持 prod 或 dev，当前: $MODE"
    exit 1
    ;;
esac
