# aiFind（智能采集运营平台）

面向 CBSS 采集任务编排、参数管理与运维监控的前后端一体化平台（FastAPI + React + Vite）。

## 1. 开发环境要求

- `Python` >= 3.10（推荐 3.11）
- `Node.js` >= 18（推荐 20 LTS）
- `npm` >= 9
- macOS / Linux（Windows 建议使用 WSL2）

可选（用于端口排查）：
- `lsof`

## 2. 拉取代码

```bash
git clone https://github.com/Mrrabbitan/aiFind.git
cd aiFind
```

## 3. 依赖安装

### 后端依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 前端依赖

```bash
cd frontend
npm install
cd ..
```

## 4. 本地启动（推荐）

### 开发联调模式（热更新）

一条命令并行启动前后端：

```bash
chmod +x ./start.sh ./start-dev.sh
./start-dev.sh
# 或 ./start.sh --mode dev
```

访问地址：
- 前端（Vite）：`http://localhost:5173`
- 后端 API：`http://localhost:8000`
- Swagger：`http://localhost:8000/docs`

### 生产/演示模式（单端口）

会构建前端并由 FastAPI 静态托管：

```bash
chmod +x ./start.sh
./start.sh
```

访问地址：
- Web：`http://localhost:8000`
- API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/api/health`

## 5. 启动参数说明

- `--mode prod|dev`：选择启动模式（默认 `prod`）
- `--rebuild-frontend`：强制重新构建 `frontend/dist`（仅 `prod` 模式）
- `--no-install`：跳过 `pip/npm` 安装步骤

示例：

```bash
./start.sh --mode prod --rebuild-frontend
./start.sh --mode dev --no-install
```

## 6. 停止服务

- `prod` 模式：终端按 `Ctrl+C`
- `dev` 模式：终端按 `Ctrl+C`（会同时关闭前后端进程）

## 7. 二次开发指引

### 目录结构（核心）

```text
aiFind/
├── backend/                 # FastAPI 业务后端
│   ├── routers/             # API 路由
│   ├── services/            # 业务与解析服务
│   ├── models.py            # 数据模型
│   └── database.py          # SQLite 连接
├── frontend/                # React 前端
│   ├── src/pages/           # 页面
│   ├── src/components/      # 组件
│   └── vite.config.js       # 开发代理配置
├── main.py                  # 应用入口
├── requirements.txt         # Python 依赖
├── start.sh                 # 一键启动主脚本
└── start-dev.sh             # 开发模式快捷脚本
```

### 常见修改入口

- 新增后端接口：`backend/routers/`
- 新增解析/业务能力：`backend/services/`
- 新增页面：`frontend/src/pages/` 并在 `frontend/src/App.jsx` 注册路由
- 调整侧边栏菜单：`frontend/src/components/Layout.jsx`

## 8. 常见问题排查

### 页面改了但没生效

- 开发模式请访问 `http://localhost:5173`，不要访问 `8000`
- 强制刷新浏览器（`Cmd + Shift + R`）
- 如仍无效，重启 `./start-dev.sh`

### 端口占用

- 后端：`8000`
- 前端：`5173`

释放占用（macOS/Linux）：

```bash
lsof -tiTCP:8000 -sTCP:LISTEN | xargs kill -9
lsof -tiTCP:5173 -sTCP:LISTEN | xargs kill -9
```

### Python 或 Node 依赖异常

```bash
rm -rf frontend/node_modules
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

## 9. 代码提交建议

- 提交前运行开发模式进行基本回归
- 优先保持后端接口字段与前端表单一致
- 提交信息建议使用 `feat/fix/refactor` 前缀

