"""
Telemetry_Sync 节点

职责：从 ROS2/仿真同步客观状态：位姿、电量、忙闲、距离
输入：ROS2 topics/actions
输出：更新 robot.pose/twist/battery_pct/battery_state/resources/distance_to_target
"""

from dataclasses import replace
from typing import Dict, Any, Optional, Protocol

from robot_brain.core.models import Pose, Twist
from robot_brain.core.state import BrainState, RobotState
from .base import IKernelNode


class ITelemetrySource(Protocol):
    """遥测数据源接口"""
    
    def get_pose(self) -> Optional[Dict[str, float]]:
        """获取位姿数据"""
        ...
    
    def get_twist(self) -> Optional[Dict[str, float]]:
        """获取速度数据"""
        ...
    
    def get_battery(self) -> Optional[Dict[str, Any]]:
        """获取电池数据"""
        ...
    
    def get_resources(self) -> Optional[Dict[str, bool]]:
        """获取资源占用状态"""
        ...


class MockTelemetrySource:
    """模拟遥测数据源（用于测试）"""
    
    def __init__(self):
        self._pose = None
        self._twist = None
        self._battery = None
        self._resources = None
    
    def set_pose(self, pose: Dict[str, float]):
        self._pose = pose
    
    def set_twist(self, twist: Dict[str, float]):
        self._twist = twist
    
    def set_battery(self, battery: Dict[str, Any]):
        self._battery = battery
    
    def set_resources(self, resources: Dict[str, bool]):
        self._resources = resources
    
    def get_pose(self) -> Optional[Dict[str, float]]:
        return self._pose
    
    def get_twist(self) -> Optional[Dict[str, float]]:
        return self._twist
    
    def get_battery(self) -> Optional[Dict[str, Any]]:
        return self._battery
    
    def get_resources(self) -> Optional[Dict[str, bool]]:
        return self._resources


class TelemetrySyncNode(IKernelNode):
    """遥测数据同步节点"""
    
    def __init__(self, telemetry_source: Optional[ITelemetrySource] = None):
        self._source = telemetry_source or MockTelemetrySource()
    
    def execute(self, state: BrainState) -> BrainState:
        """同步遥测数据到状态"""
        new_robot = self._sync_robot_state(state.robot)
        
        # 计算到目标的距离
        distance = self._calculate_distance_to_target(new_robot, state)
        new_robot = replace(new_robot, distance_to_target=distance)
        
        # 记录日志
        new_log = state.trace.log.copy()
        new_log.append(
            f"[Telemetry_Sync] 位置: ({new_robot.pose.x:.2f}, {new_robot.pose.y:.2f}), "
            f"电量: {new_robot.battery_pct:.1f}%, 距离目标: {distance:.2f}m"
        )
        new_trace = replace(state.trace, log=new_log)
        
        return replace(state, robot=new_robot, trace=new_trace)
    
    def _sync_robot_state(self, current: RobotState) -> RobotState:
        """同步机器人状态"""
        new_pose = current.pose
        new_twist = current.twist
        new_battery_pct = current.battery_pct
        new_battery_state = current.battery_state
        new_resources = current.resources.copy()
        
        # 同步位姿
        pose_data = self._source.get_pose()
        if pose_data:
            new_pose = Pose(
                x=pose_data.get("x", current.pose.x),
                y=pose_data.get("y", current.pose.y),
                z=pose_data.get("z", current.pose.z),
                orientation_w=pose_data.get("orientation_w", current.pose.orientation_w),
                orientation_x=pose_data.get("orientation_x", current.pose.orientation_x),
                orientation_y=pose_data.get("orientation_y", current.pose.orientation_y),
                orientation_z=pose_data.get("orientation_z", current.pose.orientation_z),
            )
        
        # 同步速度
        twist_data = self._source.get_twist()
        if twist_data:
            new_twist = Twist(
                linear_x=twist_data.get("linear_x", current.twist.linear_x),
                linear_y=twist_data.get("linear_y", current.twist.linear_y),
                linear_z=twist_data.get("linear_z", current.twist.linear_z),
                angular_x=twist_data.get("angular_x", current.twist.angular_x),
                angular_y=twist_data.get("angular_y", current.twist.angular_y),
                angular_z=twist_data.get("angular_z", current.twist.angular_z),
            )
        
        # 同步电池
        battery_data = self._source.get_battery()
        if battery_data:
            new_battery_pct = battery_data.get("percentage", current.battery_pct)
            new_battery_state = battery_data.get("state", current.battery_state)
        
        # 同步资源状态
        resources_data = self._source.get_resources()
        if resources_data:
            new_resources.update(resources_data)
        
        return RobotState(
            pose=new_pose,
            twist=new_twist,
            battery_pct=new_battery_pct,
            battery_state=new_battery_state,
            resources=new_resources,
            distance_to_target=current.distance_to_target
        )
    
    def _calculate_distance_to_target(self, robot: RobotState, state: BrainState) -> float:
        """计算到当前任务目标的距离"""
        if not state.tasks.active_task_id:
            return 0.0
        
        # 查找活动任务
        active_task = None
        for task in state.tasks.queue:
            if task.task_id == state.tasks.active_task_id:
                active_task = task
                break
        
        if not active_task or "target_pose" not in active_task.metadata:
            return robot.distance_to_target  # 保持原值
        
        target = active_task.metadata["target_pose"]
        dx = target.get("x", 0) - robot.pose.x
        dy = target.get("y", 0) - robot.pose.y
        return (dx ** 2 + dy ** 2) ** 0.5
