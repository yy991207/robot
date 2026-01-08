"""状态接口"""

from fastapi import APIRouter, Request


router = APIRouter()


@router.get("/status")
async def get_status(request: Request):
    """获取机器人状态"""
    app_state = request.app.state.app_state
    
    if not app_state.brain or not app_state.brain.state:
        return {"error": "未初始化"}
    
    state = app_state.brain.state
    theta = app_state._quaternion_to_yaw(state.robot.pose)
    
    return {
        "robot": {
            "x": state.robot.pose.x,
            "y": state.robot.pose.y,
            "theta": theta,
            "battery_pct": state.robot.battery_pct,
            "battery_state": state.robot.battery_state,
            "distance_to_target": state.robot.distance_to_target
        },
        "task": {
            "active_task_id": state.tasks.active_task_id,
            "goal": state.tasks.queue[0].goal if state.tasks.queue else None,
            "mode": state.tasks.mode.value,
            "queue_length": len(state.tasks.queue)
        },
        "skills": {
            "running": [s.skill_name for s in state.skills.running]
        },
        "decision": {
            "type": state.react.decision.type.value if state.react.decision else None,
            "reason": state.react.decision.reason if state.react.decision else None
        }
    }
