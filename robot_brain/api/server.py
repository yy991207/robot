"""
FastAPI 服务器主入口
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from robot_brain.api.routes import chat, command, map_routes, status
from robot_brain.api.websocket import router as ws_router
from robot_brain.api.state import AppState


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    app.state.app_state = AppState()
    await app.state.app_state.initialize()
    
    # 启动后台任务
    task = asyncio.create_task(app.state.app_state.run_simulation_loop())
    
    yield
    
    # 关闭时清理
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="Robot Brain API",
        description="机器人大脑 Web 交互接口",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # 注册路由
    app.include_router(chat.router, prefix="/api", tags=["chat"])
    app.include_router(command.router, prefix="/api", tags=["command"])
    app.include_router(map_routes.router, prefix="/api", tags=["map"])
    app.include_router(status.router, prefix="/api", tags=["status"])
    app.include_router(ws_router, tags=["websocket"])
    
    # 静态文件
    web_dir = Path(__file__).parent.parent.parent / "web"
    if web_dir.exists():
        app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")
        
        @app.get("/")
        async def index():
            return FileResponse(str(web_dir / "index.html"))
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("robot_brain.api.server:app", host="0.0.0.0", port=8000, reload=True)
