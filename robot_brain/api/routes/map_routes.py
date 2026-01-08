"""地图接口"""

from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid


router = APIRouter()


# 区域定义
ZONES = [
    {"name": "kitchen", "x": 2, "y": 2, "radius": 1, "color": "#4CAF50"},
    {"name": "living_room", "x": 10, "y": 5, "radius": 1, "color": "#2196F3"},
    {"name": "bedroom", "x": 2, "y": 7, "radius": 1, "color": "#9C27B0"},
    {"name": "bathroom", "x": 7, "y": 12, "radius": 1, "color": "#00BCD4"},
    {"name": "charging_station", "x": -1, "y": 1, "radius": 0.5, "color": "#FF9800"},
]


class Obstacle(BaseModel):
    id: Optional[str] = None
    x: float
    y: float
    width: float = 1.0
    height: float = 1.0


class ObstacleRequest(BaseModel):
    action: str  # add | remove | move
    obstacle: Obstacle


@router.get("/map")
async def get_map(request: Request):
    """获取地图信息"""
    app_state = request.app.state.app_state
    
    return {
        "width": 16,
        "height": 16,
        "zones": ZONES,
        "obstacles": app_state.obstacles
    }


@router.post("/map/obstacle")
async def operate_obstacle(req: ObstacleRequest, request: Request):
    """操作障碍物"""
    app_state = request.app.state.app_state
    
    robot_reaction = {"detected": False, "action": "none", "new_path": None}
    
    if req.action == "add":
        obstacle = req.obstacle.model_dump()
        if not obstacle.get("id"):
            obstacle["id"] = f"obs_{uuid.uuid4().hex[:8]}"
        app_state.add_obstacle(obstacle)
        
        # 检测是否影响机器人路径
        robot_reaction = _check_path_conflict(app_state, obstacle)
        
    elif req.action == "remove":
        app_state.remove_obstacle(req.obstacle.id)
        
    elif req.action == "move":
        app_state.move_obstacle(req.obstacle.id, req.obstacle.x, req.obstacle.y)
        obstacle = req.obstacle.model_dump()
        robot_reaction = _check_path_conflict(app_state, obstacle)
    
    # 广播障碍物更新
    await app_state.broadcast_all({
        "type": "obstacles_update",
        "data": {"obstacles": app_state.obstacles}
    })
    
    return {
        "success": True,
        "obstacles": app_state.obstacles,
        "robot_reaction": robot_reaction
    }


def _check_path_conflict(app_state, obstacle: dict) -> dict:
    """检查障碍物是否与机器人路径冲突"""
    if not app_state.brain or not app_state.brain.state:
        return {"detected": False, "action": "none", "new_path": None}
    
    state = app_state.brain.state
    robot_x = state.robot.pose.x
    robot_y = state.robot.pose.y
    
    obs_x = obstacle["x"]
    obs_y = obstacle["y"]
    obs_w = obstacle.get("width", 1)
    obs_h = obstacle.get("height", 1)
    
    # 简单检测：障碍物是否在机器人附近
    distance = ((robot_x - obs_x) ** 2 + (robot_y - obs_y) ** 2) ** 0.5
    
    if distance < 3:
        return {
            "detected": True,
            "action": "replanning",
            "new_path": None  # 实际路径规划由模拟器处理
        }
    
    return {"detected": False, "action": "none", "new_path": None}
