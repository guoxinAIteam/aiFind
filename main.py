"""智能采集运营平台 — 入口"""
import os, sys

# 将当前目录添加到 Python 路径的开头，确保能正确导入本地模块
sys.path.insert(0, os.path.dirname(__file__))

# 导入 FastAPI 相关模块
from fastapi import FastAPI
# 导入 Response 类，用于自定义响应处理
from fastapi.responses import Response
# 导入 CORS 中间件，用于处理跨域请求
from fastapi.middleware.cors import CORSMiddleware
# 导入静态文件服务模块
from fastapi.staticfiles import StaticFiles

# 导入数据库引擎和基础类
from backend.database import engine, Base
# 导入所有模型（使用 * 导入确保所有模型都被注册）
from backend.models import *  # noqa: ensure all models registered
# 导入轻量 schema 对齐逻辑（为已有表追加本期新增列）
from backend.migrations import ensure_schema
# 导入数据初始化函数
from backend.seed import seed
# 导入各个功能模块的路由
from backend.routers import dashboard, flows, params, monitor, knowledge, manual, skills, auth
# 导入文档解析路由
from backend.routers import doc_parse
# 导入上游 AI 解析路由
from backend.routers import parse

# 创建数据库表结构（如果表不存在）
Base.metadata.create_all(bind=engine)
# 为已有表补齐本期新增列（幂等）
ensure_schema(engine)
# 初始化基础数据
seed()

# 创建 FastAPI 应用实例，设置应用标题和版本
app = FastAPI(title="智能采集运营平台", version="1.0.0")
# 添加 CORS 中间件，允许所有来源、方法和头部的跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态采集场景：上下游调用审计中间件（/api/parse /api/mcp /api/flows/static*）
from backend.middleware.agent_audit import AgentAuditMiddleware
app.add_middleware(AgentAuditMiddleware)

# 定义健康检查路由，用于监控应用状态
@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


# 注册各个功能模块的路由
# 仪表板路由
app.include_router(dashboard.router)
# 流程管理路由
app.include_router(flows.router)
# 参数管理路由
app.include_router(params.router)
# 监控路由
app.include_router(monitor.router)
# 知识库路由
app.include_router(knowledge.router)
# 手动操作路由
app.include_router(manual.router)
# 技能管理路由
app.include_router(skills.router)
# 认证路由
app.include_router(auth.router)
# 文档解析路由
app.include_router(doc_parse.router)
# 上游 AI 解析路由（静态采集场景）
app.include_router(parse.router)
# MCP 工具注册表 REST 入口
from backend.routers import mcp as mcp_router
app.include_router(mcp_router.router)
# 3D 全景大屏拓扑 API
from backend.routers import topology as topology_router
app.include_router(topology_router.router)


# 自定义静态文件服务类，用于支持 SPA（单页应用）的前端路由
class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> Response:
        try:
            # 尝试返回请求的静态文件
            return await super().get_response(path, scope)
        except Exception as exc:
            # 处理 SPA 深链路刷新问题
            # 当请求的文件不存在（404）时，回退到 index.html 交给前端路由处理
            if getattr(exc, "status_code", None) == 404:
                return await super().get_response("index.html", scope)
            # 其他异常直接抛出
            raise


# 构建前端静态文件目录路径
dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
# 如果前端构建目录存在，则挂载静态文件服务
if os.path.isdir(dist):
    # 挂载自定义的 SPA 静态文件服务，处理前端路由
    app.mount("/", SPAStaticFiles(directory=dist, html=True), name="spa")


# 当直接运行此脚本时，启动开发服务器
if __name__ == "__main__":
    import uvicorn

    # 可通过环境变量 PORT 覆盖（默认 8000；端口被占用时换空闲端口）
    _port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=_port, reload=True)
