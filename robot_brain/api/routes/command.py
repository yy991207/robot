"""命令接口"""

from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional


router = APIRouter()


class CommandRequest(BaseModel):
    command: str
    thread_id: Optional[str] = "default"


class CommandResponse(BaseModel):
    success: bool
    task_id: Optional[str] = None
    message: str


@router.post("/command", response_model=CommandResponse)
async def execute_command(req: CommandRequest, request: Request):
    """执行命令"""
    app_state = request.app.state.app_state
    
    app_state.brain.inject_user_input(req.command)
    await app_state.brain.run_once()
    
    state = app_state.brain.state
    task_id = state.tasks.active_task_id
    
    message = ""
    if state.react.decision:
        message = state.react.decision.reason
    
    return CommandResponse(
        success=True,
        task_id=task_id,
        message=message or "命令已执行"
    )


@router.post("/robot/stop")
async def stop_robot(request: Request):
    """紧急停止"""
    app_state = request.app.state.app_state
    app_state.brain.inject_user_input("stop")
    await app_state.brain.run_once()
    return {"success": True, "message": "已停止"}


@router.post("/robot/pause")
async def pause_robot(request: Request):
    """暂停"""
    app_state = request.app.state.app_state
    app_state.brain.inject_user_input("pause")
    await app_state.brain.run_once()
    return {"success": True, "message": "已暂停"}


@router.post("/robot/resume")
async def resume_robot(request: Request):
    """继续"""
    app_state = request.app.state.app_state
    app_state.brain.inject_user_input("resume")
    await app_state.brain.run_once()
    return {"success": True, "message": "已继续"}
