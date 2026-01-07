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
        self._target_theta: Optional[float] = None
        self._behavior_tree: Optional[str] = None
    
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
    
    def set_target_pose(self, x: float, y: float, theta: float = 0.0, behavior_tree: str = ""):
        """直接设置目标坐标和朝向"""
        self._target_x = x
        self._target_y = y
        self._target_theta = theta
        self._behavior_tree = behavior_tree
    
    def step(self, state: BrainState) -> BrainState:
        """执行一步模拟，更新机器人位置和朝向"""
        if self._target_x is None or self._target_y is None:
            # 从运行中的技能获取目标
            self._extract_target_from_skills(state)
        
        if self._target_x is None:
            return state
        
        # 计算当前位置到目标的距离
        current_x = state.robot.pose.x
        current_y = state.robot.pose.y
        current_theta = math.atan2(
            state.robot.pose.orientation_z, 
            state.robot.pose.orientation_w
        ) * 2  # 简化的四元数转欧拉角
        
        dx = self._target_x - current_x
        dy = self._target_y - current_y
        distance = math.sqrt(dx * dx + dy * dy)
        
        # 检查位置是否到达
        position_reached = distance < 0.1
        
        # 检查朝向是否到达（如果有目标朝向）
        orientation_reached = True
        if self._target_theta is not None:
            theta_diff = abs(self._target_theta - current_theta)
            # 处理角度环绕
            if theta_diff > math.pi:
                theta_diff = 2 * math.pi - theta_diff
            orientation_reached = theta_diff < 0.1
        
        if position_reached and orientation_reached:
            # 已到达目标
            self._target_x = None
            self._target_y = None
            self._target_theta = None
            self._behavior_tree = None
            return state
        
        new_x = current_x
        new_y = current_y
        new_theta = current_theta
        
        # 移动策略根据行为树调整
        move_speed = self._get_move_speed()
        turn_speed = 0.5  # 转向速度
        
        if not position_reached:
            # 先移动到位置
            if distance > 0:
                move_x = (dx / distance) * min(move_speed, distance)
                move_y = (dy / distance) * min(move_speed, distance)
                new_x = current_x + move_x
                new_y = current_y + move_y
        elif self._target_theta is not None and not orientation_reached:
            # 位置到达后调整朝向
            theta_diff = self._target_theta - current_theta
            # 选择最短转向路径
            if theta_diff > math.pi:
                theta_diff -= 2 * math.pi
            elif theta_diff < -math.pi:
                theta_diff += 2 * math.pi
            
            turn_amount = min(turn_speed, abs(theta_diff))
            if theta_diff > 0:
                new_theta = current_theta + turn_amount
            else:
                new_theta = current_theta - turn_amount
        
        # 更新位姿（简化的四元数）
        new_pose = Pose(
            x=new_x,
            y=new_y,
            z=state.robot.pose.z,
            orientation_w=math.cos(new_theta / 2),
            orientation_x=0,
            orientation_y=0,
            orientation_z=math.sin(new_theta / 2)
        )
        
        # 更新电量
        battery_drain = self._get_battery_drain()
        new_battery = max(0, state.robot.battery_pct - battery_drain)
        
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
                    self._target_theta = params.get("target_theta", 0.0)
                    self._behavior_tree = params.get("behavior_tree", "")
                    return
                # 从目标名称解析
                target = params.get("target", "")
                if target:
                    if self.set_target(target):
                        self._target_theta = params.get("target_theta", 0.0)
                        self._behavior_tree = params.get("behavior_tree", "")
                    return
        
        # 从任务目标解析
        if state.tasks.active_task_id:
            for task in state.tasks.queue:
                if task.task_id == state.tasks.active_task_id:
                    goal = task.goal
                    if goal.startswith("navigate_to:"):
                        target = goal.split(":", 1)[1]
                        if self.set_target(target):
                            # 从任务元数据获取朝向和行为树
                            metadata = task.metadata
                            self._target_theta = metadata.get("target_theta", 0.0)
                            self._behavior_tree = metadata.get("behavior_tree", "")
                        return
    
    def _get_move_speed(self) -> float:
        """根据行为树获取移动速度"""
        if self._behavior_tree == "careful_navigation.xml":
            return 0.5  # 谨慎模式：慢速
        elif self._behavior_tree == "fast_navigation.xml":
            return 2.0  # 快速模式：高速
        else:
            return self.MOVE_SPEED  # 默认速度
    
    def _get_battery_drain(self) -> float:
        """根据行为树获取电量消耗"""
        if self._behavior_tree == "careful_navigation.xml":
            return 0.3  # 谨慎模式：省电
        elif self._behavior_tree == "fast_navigation.xml":
            return 1.0  # 快速模式：耗电
        else:
            return self.BATTERY_DRAIN  # 默认消耗
    
    def is_at_target(self, state: BrainState) -> bool:
        """检查是否已到达目标（位置和朝向）"""
        if self._target_x is None:
            return True
        
        # 检查位置
        dx = self._target_x - state.robot.pose.x
        dy = self._target_y - state.robot.pose.y
        position_reached = math.sqrt(dx * dx + dy * dy) < 0.5
        
        # 检查朝向
        if self._target_theta is not None:
            current_theta = math.atan2(
                state.robot.pose.orientation_z, 
                state.robot.pose.orientation_w
            ) * 2
            theta_diff = abs(self._target_theta - current_theta)
            if theta_diff > math.pi:
                theta_diff = 2 * math.pi - theta_diff
            orientation_reached = theta_diff < 0.2
            return position_reached and orientation_reached
        
        return position_reached
    
    def get_distance_to_target(self, state: BrainState) -> float:
        """获取到目标的距离"""
        if self._target_x is None:
            return 0
        
        dx = self._target_x - state.robot.pose.x
        dy = self._target_y - state.robot.pose.y
        return math.sqrt(dx * dx + dy * dy)
