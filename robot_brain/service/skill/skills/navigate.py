"""
NavigateToPose 技能

封装 Nav2 NavigateToPose Action
"""

from typing import Dict, Any, Optional

from robot_brain.core.enums import SkillStatus
from robot_brain.core.models import SkillResult


class NavigateToPoseSkill:
    """导航技能"""
    
    def __init__(self):
        self._active_goals: Dict[str, Dict[str, Any]] = {}
    
    async def execute(self, goal_id: str, params: Dict[str, Any]) -> None:
        """执行导航"""
        target_x = params.get("target_x", 0.0)
        target_y = params.get("target_y", 0.0)
        target_theta = params.get("target_theta", 0.0)
        behavior_tree = params.get("behavior_tree", "")
        
        self._active_goals[goal_id] = {
            "target_x": target_x,
            "target_y": target_y,
            "target_theta": target_theta,
            "behavior_tree": behavior_tree,
            "status": "RUNNING",
            "progress": 0.0,
            "distance_remaining": 0.0
        }
        
        # 实际实现中这里会调用 ROS2 Action Client
        # await self._nav2_client.send_goal(goal)
    
    async def cancel(self, goal_id: str) -> bool:
        """取消导航"""
        if goal_id not in self._active_goals:
            return False
        
        self._active_goals[goal_id]["status"] = "CANCELLED"
        
        # 实际实现中这里会调用 ROS2 Action Client cancel
        # await self._nav2_client.cancel_goal(goal_id)
        
        return True
    
    async def get_feedback(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """获取导航反馈"""
        if goal_id not in self._active_goals:
            return None
        
        goal_info = self._active_goals[goal_id]
        
        # 实际实现中这里会从 ROS2 Action 获取反馈
        # feedback = await self._nav2_client.get_feedback(goal_id)
        
        return {
            "current_pose": {"x": 0, "y": 0, "theta": 0},
            "distance_remaining": goal_info.get("distance_remaining", 0),
            "navigation_time": 0,
            "estimated_time_remaining": 0,
            "number_of_recoveries": 0
        }
    
    async def get_result(self, goal_id: str) -> Optional[SkillResult]:
        """获取导航结果"""
        if goal_id not in self._active_goals:
            return None
        
        goal_info = self._active_goals[goal_id]
        status = goal_info.get("status", "RUNNING")
        
        if status == "RUNNING":
            return None
        
        if status == "SUCCEEDED":
            return SkillResult(
                status=SkillStatus.SUCCESS,
                metrics={"navigation_time": 0}
            )
        elif status == "CANCELLED":
            return SkillResult(
                status=SkillStatus.CANCELLED,
                error_code="CANCELLED",
                error_msg="Navigation cancelled"
            )
        else:
            return SkillResult(
                status=SkillStatus.FAILED,
                error_code=goal_info.get("error_code", "UNKNOWN"),
                error_msg=goal_info.get("error_msg", "Navigation failed")
            )
    
    def set_result(self, goal_id: str, status: str, error_code: str = "", error_msg: str = ""):
        """设置结果（用于测试或外部更新）"""
        if goal_id in self._active_goals:
            self._active_goals[goal_id]["status"] = status
            self._active_goals[goal_id]["error_code"] = error_code
            self._active_goals[goal_id]["error_msg"] = error_msg
    
    def update_feedback(self, goal_id: str, distance_remaining: float, progress: float = 0.0):
        """更新反馈（用于测试或外部更新）"""
        if goal_id in self._active_goals:
            self._active_goals[goal_id]["distance_remaining"] = distance_remaining
            self._active_goals[goal_id]["progress"] = progress
