"""核心数据模型定义"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from .enums import DecisionType, InterfaceType, SkillStatus, TaskStatus


@dataclass
class Pose:
    """机器人位姿"""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    orientation_w: float = 1.0
    orientation_x: float = 0.0
    orientation_y: float = 0.0
    orientation_z: float = 0.0


@dataclass
class Twist:
    """机器人速度"""
    linear_x: float = 0.0
    linear_y: float = 0.0
    linear_z: float = 0.0
    angular_x: float = 0.0
    angular_y: float = 0.0
    angular_z: float = 0.0


@dataclass
class Task:
    """任务定义"""
    task_id: str
    goal: str
    priority: int = 0
    deadline: Optional[float] = None
    resources_required: List[str] = field(default_factory=list)
    preemptible: bool = True
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillDef:
    """技能定义"""
    name: str
    interface_type: InterfaceType = InterfaceType.ROS2_ACTION
    args_schema: Dict[str, Any] = field(default_factory=dict)
    resources_required: List[str] = field(default_factory=list)
    preemptible: bool = True
    cancel_supported: bool = True
    timeout_s: float = 60.0
    error_map: Dict[str, str] = field(default_factory=dict)
    description: str = ""


@dataclass
class RunningSkill:
    """运行中的技能"""
    goal_id: str
    skill_name: str
    start_time: float
    timeout_s: float
    resources_occupied: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillResult:
    """技能执行结果"""
    status: SkillStatus = SkillStatus.SUCCESS
    error_code: str = ""
    error_msg: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Decision:
    """LLM 决策"""
    type: DecisionType = DecisionType.CONTINUE
    reason: str = ""
    plan_patch: Optional[Dict[str, Any]] = None
    ops: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ProposedOps:
    """编译后的操作集合"""
    to_cancel: List[str] = field(default_factory=list)
    to_dispatch: List[Dict[str, Any]] = field(default_factory=list)
    to_speak: List[str] = field(default_factory=list)
    need_approval: bool = False
    approval_payload: Dict[str, Any] = field(default_factory=dict)
