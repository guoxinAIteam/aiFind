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

## 10. 静态（离线）采集决策中枢

本平台在三智能体体系中作为 **决策中枢**：向上通过 MD5 签名流式 API 调度
联通能开 AI 解析智能体，向下以 BDI 16 字段标准入参驱动离线采集执行智能体，
串联「任务发起 → AI 解析 → 参数转换 → BDI 调度 → 监控 → 异常处理 →
测试 → 上线」8 个阶段。

### 10.1 关键接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/parse/requirement` | 同步调用上游 AI 解析，落库并计算缺失字段 |
| `POST` | `/api/parse/stream` | SSE 流式版本，前端 `EventSource` / ReadableStream 消费 |
| `POST` | `/api/parse/docx` | 从 `.docx` 提取纯文本（段落+表格），供需求录入回填 |
| `POST` | `/api/parse/{id}/supplement` | 对解析结果补全缺失字段 |
| `POST` | `/api/flows/static` | 创建静态采集任务并自动推进 8 阶段（`overrides.category` 写入快照，默认 `province`） |
| `GET` | `/api/flows/static/list` | 离线采集任务列表（默认仅 `category=province`，支持 `q`/`status`/分页） |
| `GET` | `/api/flows/{id}/static` | 查询任务 + 阶段 + 解析 + BDI 绑定 + 缺失字段 |
| `POST` | `/api/flows/{id}/supplement` | 用户补全 BDI 入参后续跑 |
| `POST` | `/api/flows/{id}/supplement/import-excel` | 上传 `.xlsx`，前两列按缺失字段路径回填（不落库，仅返回键值供前端合并） |
| `GET` | `/api/mcp/tools` | 列出 MCP 工具注册表（unicom + BDI 5 个工具） |
| `POST` | `/api/mcp/tools/{name}/call` | REST 形式调用 MCP 工具（协议未就位时的降级通道） |
| `GET` | `/api/mcp/health` | 工具调用计数与健康 |

### 10.2 环境变量

复制 `.env.example` 为 `.env`（或通过 `export` 注入）：

```bash
# 上游：联通能开 AI 解析智能体
UNICOM_APP_ID=...
UNICOM_TEAM_ID=...
UNICOM_SK=...
UNICOM_API_URL=https://ai-agent.chinaunicom.cn/uia/api/robot/chat/stream/v1
# 关闭真实调用改走内置 mock（前后端联调非常有用）
UNICOM_MOCK=1

# 下游：BDI 执行智能体
BDI_BASE_URL=
BDI_KEY=
BDI_SKILL_NAME=接口规范-sftp-数据库-realease.skill
BDI_MOCK=1
```

真实凭据切勿提交仓库。本地 mock 模式下，全链路可在无上下游真实服务时跑通。

### 10.3 本地联调示意

```bash
UNICOM_MOCK=1 BDI_MOCK=1 BDI_KEY=demo ./start-dev.sh
```

浏览器访问 `http://localhost:5173/offline-collect`（省分个采操作记录列表，每页 10 条）
或 `http://localhost:5173/offline-collect/province`（录入页）：可录入需求、导入 Word（`.docx`）
回填需求文本；缺失参数补全支持导入 Excel（`.xlsx` 前两列：字段路径、取值）批量回填后再提交。
左侧实时查看 8 阶段进度，右侧为 AI 解析流式输出、补全面板与 BDI 执行回执。旧路径
`/static-collect` 会重定向到 `/offline-collect/province`。

### 10.4 模块边界

```text
backend/
├── routers/
│   ├── parse.py           # /api/parse/* 上游解析路由
│   ├── flows.py           # /api/flows/static* 8 阶段编排 + 原有 6 步模板
│   └── mcp.py             # /api/mcp/* 工具注册表 REST 入口
├── services/
│   ├── upstream/          # 联通 AI 客户端（MD5 签名、SSE 流）
│   ├── downstream/        # BDI 客户端 + BdiParams
│   ├── transform/         # upstream_to_bdi 映射器
│   ├── mcp/               # Server/Client/Registry + 工具实现
│   ├── skills/static_collect_orchestration.py  # 8 阶段模板
│   └── reliability.py     # 指数退避重试 + task_lock
├── middleware/agent_audit.py  # 上下游 REST 调用审计 + 告警事件
└── models.py              # ParseResult / BdiTaskBinding / AgentInvocation / MissingField
tests/
└── test_unicom_parser.py / test_bdi_mapper.py  # MD5 签名、映射器、Mock 客户端
```


## 11. 3D 全景大屏拓扑

将 aiFind 决策中枢的上游解析、核心编排、BDI 执行与目标端呈现为一张可旋转
缩放的 3D 拓扑大屏，实时展示采集任务的流向与节点健康度。

- 入口：侧栏 `监控中心` 下方的 `全景大屏 3D`，路径 `/topology`
- 视觉：5 层节点卡片 + 弧形连线 + Bloom 辉光 + 深空星场；每条活跃任务
  一条 CatmullRom 曲线粒子流，颜色随 `scenario / status` 切换
- HUD：顶部状态条 + 右上角 6 项实时指标 + 底部滚动事件条，事件按
  `source_system` 映射回对应节点，3.5s 内节点发光高亮
- 交互：`R` 重置视角 / `P` 暂停粒子 / `F` 全屏 / `B` 切换性能模式 /
  `Esc` 关闭详情面板；点击节点弹出右侧详情（最近 20 条 AgentInvocation +
  10 条 MonitorEvent + BDI 绑定）
- 数据链路：
  - 首帧：`GET /api/topology/snapshot` 返回 17 节点 + 28 条边 + 活跃任务 +
    HUD 统计
  - 增量：`GET /api/topology/stream` SSE 每 1.5s 推 `task_tick` 与 `event`
    delta；断开后指数退避 2/4/8s 重连，超过 3 次降级为 5s 轮询 `/snapshot`
  - 节点详情：`GET /api/topology/nodes/{key}` 每 5s 自动刷新
- 性能兜底：活跃任务 > 50 时自动开启性能模式（关闭 Bloom，光流线从 50 压至 20）
  ，也可通过 `B` 键手动切换；焦点在输入框内时快捷键不触发

对应前端模块：

```text
frontend/src/pages/Topology3D.jsx
frontend/src/pages/topology/
├── Scene.jsx / Nodes.jsx / Edges.jsx / ActiveFlows.jsx
├── Hud.jsx / DetailPanel.jsx
├── useTopologyStream.js   # snapshot + SSE + 指数退避重连 + 轮询降级 + 节点高亮
└── layout.js              # 5 层节点坐标 / 颜色常量
```

后端对应：`backend/routers/topology.py`，零新增依赖。


