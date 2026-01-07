"""
机器人位置模拟器

模拟机器人移动、电量消耗等
"""

import math
from typing import Dict, Optional
from dataclasses import dataclass

from robot_brain.core.state import BrainState
from robot_brain.core.models import Pose


@dataclass
class ZoneInfo:
    """区域信息"""
    name: str
    x: float
    y: float


class RobotSimulator:
    """机器人模拟器"""
    
    # 区域坐标
    ZONES = {
        "kitchen": ZoneInfo("kitchen", 2.0, 2.0),
        "living_room": ZoneInfo("living_room", 10.0, 5.0),
        "bedroom": ZoneInfo("bedroom", 2.0, 7.0),
        "bathroom": ZoneInfo("bathroom", 7.0, 12.0),
        "charging_station": ZoneInfo("charging_station", -1.0, 1.0),
    }
    
    # 移动速度（单位/步）
    MOVE_SPEED = 1.0
    # 电量消耗（%/步）
    BATTERY_DRAIN = 0.5
    
    def __init__(self):
        self._target_x: Optional[float] = None
        self._target_y: Optional[float] = None
    
    def set_target(self, target: str) -> bool:
        """设置目标位置"""
        target_lower = target.lower()
        
        # 查找匹配的区域
        for zone_name, zone_info in self.ZONES.items():
            if zone_name.startswith(target_lower) or target_lower in zone_name:
                self._target_x = zone_info.x
                self._target_y = zone_info.y
                return True
        
        return False
    
    def set_target_pose(self, x: float, y: float):
        """直接设置目标坐标"""
        self._target_x = x
        self._target_y = y
    
    def step(self, state: BrainState) -> BrainState:
        """执行一步模拟，更新机器人位置"""
        if self._target_x is None or self._target_y is None:
            # 从运行中的技能获取目标
            self._extract_target_from_skills(state)
        
        if self._target_x is None:
            return state
        
        # 计算当前位置到目标的距离
        current_x = state.robot.pose.x
        current_y = state.robot.pose.y
        
        dx = self._target_x - current_x
        dy = self._target_y - current_y
        distance = math.sqrt(dx * dx + dy * dy)
        
        if distance < 0.1:
            # 已到达目标
            self._target_x = None
            self._target_y = None
            return state
        
        # 计算移动方向
        if distance > 0:
            move_x = (dx / distance) * min(self.MOVE_SPEED, distance)
            move_y = (dy / distance) * min(self.MOVE_SPEED, distance)
        else:
            move_x = move_y = 0
        
        # 更新位置
        new_x = current_x + move_x
        new_y = current_y + move_y
        
        new_pose = Pose(
            x=new_x,
            y=new_y,
            z=state.robot.pose.z,
            orientation_w=state.robot.pose.orientation_w,
            orientation_x=state.robot.pose.orientation_x,
            orientation_y=state.robot.pose.orientation_y,
            orientation_z=state.robot.pose.orientation_z
        )
        
        # 更新电量
        new_battery = max(0, state.robot.battery_pct - self.BATTERY_DRAIN)
        
        # 创建新状态
        from dataclasses import replace
        new_robot = replace(
            state.robot,
            pose=new_pose,
            battery_pct=new_battery,
            distance_to_target=math.sqrt(
                (self._target_x - new_x) ** 2 + (self._target_y - new_y) ** 2
            ) if self._target_x else 0
        )
        
        return replace(state, robot=new_robot)
    
    def _extract_target_from_skills(self, state: BrainState):
        """从运行中的技能提取目标"""
        for skill in state.skills.running:
            if skill.skill_name == "NavigateToPose":
                params = skill.params
                if "target_x" in params and "target_y" in params:
                    self._target_x = params["target_x"]
                    self._target_y = params["target_y"]
                    return
                # 从目标名称解析
                target = params.get("target", "")
                if target:
                    self.set_target(target)
                    return
        
        # 从任务目标解析
        if state.tasks.active_task_id:
            for task in state.tasks.queue:
                if task.task_id == state.tasks.active_task_id:
                    goal = task.goal
                    if goal.startswith("navigate_to:"):
                        target = goal.split(":", 1)[1]
                        self.set_target(target)
                        return
    
    def is_at_target(self, state: BrainState) -> bool:
        """检查是否已到达目标"""
        if self._target_x is None:
            return True
        
        dx = self._target_x - state.robot.pose.x
        dy = self._target_y - state.robot.pose.y
        return math.sqrt(dx * dx + dy * dy) < 0.5
    
    def get_distance_to_target(self, state: BrainState) -> float:
        """获取到目标的距离"""
        if self._target_x is None:
            return 0
        
        dx = self._target_x - state.robot.pose.x
        dy = self._target_y - state.robot.pose.y
        return math.sqrt(dx * dx + dy * dy)
