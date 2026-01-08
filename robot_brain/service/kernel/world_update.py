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
        obstacles = self._source.get_obstacles() or list(state.world.obstacles)
        obstacles = self._annotate_collision_risk(state, obstacles)
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

    def _annotate_collision_risk(self, state: BrainState, obstacles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """为障碍物补充碰撞风险标记（简化实现）"""
        if not obstacles:
            return obstacles

        # 尝试从当前任务元数据提取目标点
        target_xy = None
        if state.tasks.active_task_id:
            for task in state.tasks.queue:
                if task.task_id == state.tasks.active_task_id:
                    goal = task.goal
                    if goal.startswith("navigate_to:"):
                        target = goal.split(":", 1)[1].strip()
                        zone_centers = {
                            "kitchen": (2.0, 2.0),
                            "living_room": (10.0, 5.0),
                            "bedroom": (2.0, 7.0),
                            "bathroom": (7.0, 12.0),
                            "charging_station": (-1.0, 1.0),
                            "厨房": (2.0, 2.0),
                            "客厅": (10.0, 5.0),
                            "卧室": (2.0, 7.0),
                            "浴室": (7.0, 12.0),
                            "洗手间": (7.0, 12.0),
                            "卫生间": (7.0, 12.0),
                            "充电站": (-1.0, 1.0),
                        }
                        if target in zone_centers:
                            target_xy = zone_centers[target]
                    break

        rx, ry = state.robot.pose.x, state.robot.pose.y

        def clamp(v: float, lo: float, hi: float) -> float:
            return max(lo, min(hi, v))

        def point_to_aabb_dist(px: float, py: float, cx: float, cy: float, w: float, h: float) -> float:
            # 以中心点(cx,cy)和宽高定义 AABB
            hx, hy = w / 2.0, h / 2.0
            nearest_x = clamp(px, cx - hx, cx + hx)
            nearest_y = clamp(py, cy - hy, cy + hy)
            dx = px - nearest_x
            dy = py - nearest_y
            return (dx * dx + dy * dy) ** 0.5

        def segment_to_aabb_dist(x1: float, y1: float, x2: float, y2: float, cx: float, cy: float, w: float, h: float) -> float:
            # 简化：取线段上最近点到 AABB 的距离（采样 + 端点兜底）
            # 这不是严格几何最优，但足够用于“是否有风险”判定
            best = min(
                point_to_aabb_dist(x1, y1, cx, cy, w, h),
                point_to_aabb_dist(x2, y2, cx, cy, w, h)
            )
            for t in [0.25, 0.5, 0.75]:
                px = x1 + (x2 - x1) * t
                py = y1 + (y2 - y1) * t
                best = min(best, point_to_aabb_dist(px, py, cx, cy, w, h))
            return best

        annotated: List[Dict[str, Any]] = []
        for obs in obstacles:
            # 兼容两种格式：
            # - web API 传入：x/y/width/height
            # - 原 mock 结构：position={x,y}
            cx = float(obs.get("x", obs.get("position", {}).get("x", 0.0)))
            cy = float(obs.get("y", obs.get("position", {}).get("y", 0.0)))
            w = float(obs.get("width", 1.0))
            h = float(obs.get("height", 1.0))

            # 风险判定：
            # - 机器人当前位置离障碍物太近
            # - 或者障碍物在“当前位置->目标点”的路径附近
            dist_now = point_to_aabb_dist(rx, ry, cx, cy, w, h)
            risk = dist_now < 0.6

            if (not risk) and target_xy:
                tx, ty = target_xy
                dist_path = segment_to_aabb_dist(rx, ry, tx, ty, cx, cy, w, h)
                risk = dist_path < 0.6

            new_obs = dict(obs)
            new_obs["collision_risk"] = bool(risk)
            annotated.append(new_obs)

        return annotated
    
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
                obs_type = obs.get("type", "obstacle")
                x = obs.get("x", obs.get("position", {}).get("x", 0))
                y = obs.get("y", obs.get("position", {}).get("y", 0))
                risk = obs.get("collision_risk", False)
                obstacle_desc.append(f"{obs_type}@({float(x):.1f},{float(y):.1f}) risk={risk}")
            parts.append(f"障碍物: {', '.join(obstacle_desc)}")
        
        # 任务相关
        if state.tasks.active_task_id:
            parts.append(f"当前任务: {state.tasks.active_task_id}")
            if robot.distance_to_target > 0:
                parts.append(f"距目标: {robot.distance_to_target:.1f}m")
        
        return "; ".join(parts)
    
    def _get_current_zone(self, x: float, y: float, zones: List[str]) -> Optional[str]:
        """根据坐标判断当前区域（简化实现）"""
        # 区域边界定义（更精确）
        zone_bounds = {
            "kitchen": {"x_min": 1, "x_max": 4, "y_min": 1, "y_max": 4},
            "living_room": {"x_min": 8, "x_max": 12, "y_min": 3, "y_max": 7},
            "bedroom": {"x_min": 1, "x_max": 4, "y_min": 6, "y_max": 9},
            "bathroom": {"x_min": 6, "x_max": 9, "y_min": 11, "y_max": 14},
            "charging_station": {"x_min": -2, "x_max": 0, "y_min": 0, "y_max": 2},
        }
        
        for zone in zones:
            if zone in zone_bounds:
                bounds = zone_bounds[zone]
                if (bounds["x_min"] <= x <= bounds["x_max"] and
                    bounds["y_min"] <= y <= bounds["y_max"]):
                    return zone
        
        return None
