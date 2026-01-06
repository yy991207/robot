"""
World_Update 节点

职责：更新世界摘要（给 LLM 与仲裁用）
输入：仿真传感器或仿真假值
输出：更新 world.summary
"""

from dataclasses import replace
from typing import List, Dict, Any, Optional, Protocol

from robot_brain.core.state import BrainState, WorldState
from .base import IKernelNode


class IWorldSource(Protocol):
    """世界数据源接口"""
    
    def get_zones(self) -> List[str]:
        """获取语义区域列表"""
        ...
    
    def get_obstacles(self) -> List[Dict[str, Any]]:
        """获取障碍物信息"""
        ...
    
    def get_zone_status(self, zone: str) -> Dict[str, Any]:
        """获取区域状态"""
        ...


class MockWorldSource:
    """模拟世界数据源"""
    
    def __init__(self):
        self._zones = ["kitchen", "living_room", "bedroom", "bathroom", "charging_station"]
        self._obstacles = []
        self._zone_status = {}
    
    def set_zones(self, zones: List[str]):
        self._zones = zones
    
    def set_obstacles(self, obstacles: List[Dict[str, Any]]):
        self._obstacles = obstacles
    
    def set_zone_status(self, zone: str, status: Dict[str, Any]):
        self._zone_status[zone] = status
    
    def get_zones(self) -> List[str]:
        return self._zones
    
    def get_obstacles(self) -> List[Dict[str, Any]]:
        return self._obstacles
    
    def get_zone_status(self, zone: str) -> Dict[str, Any]:
        return self._zone_status.get(zone, {"accessible": True})


class WorldUpdateNode(IKernelNode):
    """世界模型更新节点"""
    
    def __init__(self, world_source: Optional[IWorldSource] = None):
        self._source = world_source or MockWorldSource()
    
    def execute(self, state: BrainState) -> BrainState:
        """更新世界状态"""
        zones = self._source.get_zones()
        obstacles = self._source.get_obstacles()
        summary = self._generate_summary(state, zones, obstacles)
        
        new_world = WorldState(
            summary=summary,
            zones=zones,
            obstacles=obstacles
        )
        
        # 记录日志
        new_log = state.trace.log.copy()
        new_log.append(f"[World_Update] 区域数: {len(zones)}, 障碍物数: {len(obstacles)}")
        new_trace = replace(state.trace, log=new_log)
        
        return replace(state, world=new_world, trace=new_trace)
    
    def _generate_summary(self, state: BrainState, zones: List[str], obstacles: List[Dict[str, Any]]) -> str:
        """生成世界摘要"""
        parts = []
        
        # 机器人位置描述
        robot = state.robot
        current_zone = self._get_current_zone(robot.pose.x, robot.pose.y, zones)
        if current_zone:
            parts.append(f"机器人当前位于{current_zone}")
        else:
            parts.append(f"机器人位于({robot.pose.x:.1f}, {robot.pose.y:.1f})")
        
        # 可用区域
        accessible_zones = []
        for zone in zones:
            status = self._source.get_zone_status(zone)
            if status.get("accessible", True):
                accessible_zones.append(zone)
        
        if accessible_zones:
            parts.append(f"可达区域: {', '.join(accessible_zones)}")
        
        # 障碍物信息
        if obstacles:
            obstacle_desc = []
            for obs in obstacles[:3]:  # 最多显示3个
                obs_type = obs.get("type", "unknown")
                obs_pos = obs.get("position", {})
                obstacle_desc.append(f"{obs_type}@({obs_pos.get('x', 0):.1f},{obs_pos.get('y', 0):.1f})")
            parts.append(f"障碍物: {', '.join(obstacle_desc)}")
        
        # 任务相关
        if state.tasks.active_task_id:
            parts.append(f"当前任务: {state.tasks.active_task_id}")
            if robot.distance_to_target > 0:
                parts.append(f"距目标: {robot.distance_to_target:.1f}m")
        
        return "; ".join(parts)
    
    def _get_current_zone(self, x: float, y: float, zones: List[str]) -> Optional[str]:
        """根据坐标判断当前区域（简化实现）"""
        # 简化的区域映射，实际应该用更复杂的几何判断
        zone_bounds = {
            "kitchen": {"x_min": 0, "x_max": 5, "y_min": 0, "y_max": 5},
            "living_room": {"x_min": 5, "x_max": 15, "y_min": 0, "y_max": 10},
            "bedroom": {"x_min": 0, "x_max": 5, "y_min": 5, "y_max": 10},
            "bathroom": {"x_min": 5, "x_max": 10, "y_min": 10, "y_max": 15},
            "charging_station": {"x_min": -2, "x_max": 0, "y_min": 0, "y_max": 2},
        }
        
        for zone in zones:
            if zone in zone_bounds:
                bounds = zone_bounds[zone]
                if (bounds["x_min"] <= x <= bounds["x_max"] and
                    bounds["y_min"] <= y <= bounds["y_max"]):
                    return zone
        
        return None
