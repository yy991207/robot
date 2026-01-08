"""统一状态模型定义"""

import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

from .enums import Mode, UserInterruptType, DecisionType, SkillStatus, TaskStatus, InterfaceType
from .models import Pose, Twist, Task, SkillDef, RunningSkill, SkillResult, Decision, ProposedOps


@dataclass
class HCIState:
    """人机交互状态"""
    user_utterance: str = ""
    user_interrupt: UserInterruptType = UserInterruptType.NONE
    interrupt_payload: Dict[str, Any] = field(default_factory=dict)
    approval_response: Optional[Dict[str, Any]] = None


@dataclass
class WorldState:
    """世界状态"""
    summary: str = ""
    zones: List[str] = field(default_factory=list)
    obstacles: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RobotState:
    """机器人状态"""
    pose: Pose = field(default_factory=Pose)
    home_pose: Pose = field(default_factory=Pose)
    twist: Twist = field(default_factory=Twist)
    battery_pct: float = 100.0
    battery_state: str = "FULL"
    resources: Dict[str, bool] = field(default_factory=lambda: {
        "base_busy": False,
        "arm_busy": False,
        "gripper_busy": False
    })
    distance_to_target: float = 0.0


@dataclass
class TasksState:
    """任务状态"""
    inbox: List[Dict[str, Any]] = field(default_factory=list)
    queue: List[Task] = field(default_factory=list)
    active_task_id: Optional[str] = None
    mode: Mode = Mode.IDLE
    preempt_flag: bool = False
    preempt_reason: str = ""


@dataclass
class SkillsState:
    """技能状态"""
    registry: Dict[str, SkillDef] = field(default_factory=dict)
    running: List[RunningSkill] = field(default_factory=list)
    last_result: Optional[SkillResult] = None


@dataclass
class ReactState:
    """ReAct 内环状态"""
    iter: int = 0
    observation: Dict[str, Any] = field(default_factory=dict)
    decision: Optional[Decision] = None
    proposed_ops: Optional[ProposedOps] = None
    stop_reason: str = ""


@dataclass
class TraceState:
    """追踪状态"""
    log: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BrainState:
    """机器人大脑统一状态"""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    hci: HCIState = field(default_factory=HCIState)
    world: WorldState = field(default_factory=WorldState)
    robot: RobotState = field(default_factory=RobotState)
    tasks: TasksState = field(default_factory=TasksState)
    skills: SkillsState = field(default_factory=SkillsState)
    react: ReactState = field(default_factory=ReactState)
    trace: TraceState = field(default_factory=TraceState)


    def serialize(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self._to_dict(), ensure_ascii=False, indent=2)

    def _to_dict(self) -> Dict[str, Any]:
        """转换为字典，处理枚举和嵌套对象"""
        def convert(obj: Any) -> Any:
            if hasattr(obj, 'value'):  # Enum
                return obj.value
            elif hasattr(obj, '__dataclass_fields__'):  # dataclass
                return {k: convert(v) for k, v in asdict(obj).items()}
            elif isinstance(obj, list):
                return [convert(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            return obj
        return convert(self)

    @classmethod
    def deserialize(cls, data: str) -> "BrainState":
        """从 JSON 字符串反序列化"""
        d = json.loads(data)
        return cls._from_dict(d)

    @classmethod
    def _from_dict(cls, d: Dict[str, Any]) -> "BrainState":
        """从字典构建状态对象"""
        hci = HCIState(
            user_utterance=d.get("hci", {}).get("user_utterance", ""),
            user_interrupt=UserInterruptType(d.get("hci", {}).get("user_interrupt", "NONE")),
            interrupt_payload=d.get("hci", {}).get("interrupt_payload", {}),
            approval_response=d.get("hci", {}).get("approval_response")
        )
        
        world = WorldState(
            summary=d.get("world", {}).get("summary", ""),
            zones=d.get("world", {}).get("zones", []),
            obstacles=d.get("world", {}).get("obstacles", [])
        )
        
        robot_d = d.get("robot", {})
        pose_d = robot_d.get("pose", {})
        home_pose_d = robot_d.get("home_pose", {})
        twist_d = robot_d.get("twist", {})
        robot = RobotState(
            pose=Pose(**pose_d) if pose_d else Pose(),
            home_pose=Pose(**home_pose_d) if home_pose_d else Pose(),
            twist=Twist(**twist_d) if twist_d else Twist(),
            battery_pct=robot_d.get("battery_pct", 100.0),
            battery_state=robot_d.get("battery_state", "FULL"),
            resources=robot_d.get("resources", {"base_busy": False, "arm_busy": False, "gripper_busy": False}),
            distance_to_target=robot_d.get("distance_to_target", 0.0)
        )
        
        tasks_d = d.get("tasks", {})
        queue = []
        for t in tasks_d.get("queue", []):
            queue.append(Task(
                task_id=t["task_id"],
                goal=t["goal"],
                priority=t.get("priority", 0),
                deadline=t.get("deadline"),
                resources_required=t.get("resources_required", []),
                preemptible=t.get("preemptible", True),
                status=TaskStatus(t.get("status", "PENDING")),
                created_at=t.get("created_at", 0.0),
                metadata=t.get("metadata", {})
            ))
        tasks = TasksState(
            inbox=tasks_d.get("inbox", []),
            queue=queue,
            active_task_id=tasks_d.get("active_task_id"),
            mode=Mode(tasks_d.get("mode", "IDLE")),
            preempt_flag=tasks_d.get("preempt_flag", False),
            preempt_reason=tasks_d.get("preempt_reason", "")
        )
        
        skills_d = d.get("skills", {})
        registry = {}
        for name, sd in skills_d.get("registry", {}).items():
            registry[name] = SkillDef(
                name=sd["name"],
                interface_type=InterfaceType(sd.get("interface_type", "ros2_action")),
                args_schema=sd.get("args_schema", {}),
                resources_required=sd.get("resources_required", []),
                preemptible=sd.get("preemptible", True),
                cancel_supported=sd.get("cancel_supported", True),
                timeout_s=sd.get("timeout_s", 60.0),
                error_map=sd.get("error_map", {}),
                description=sd.get("description", "")
            )
        running = []
        for rs in skills_d.get("running", []):
            running.append(RunningSkill(
                goal_id=rs["goal_id"],
                skill_name=rs["skill_name"],
                start_time=rs["start_time"],
                timeout_s=rs["timeout_s"],
                resources_occupied=rs.get("resources_occupied", []),
                params=rs.get("params", {})
            ))
        last_result = None
        if skills_d.get("last_result"):
            lr = skills_d["last_result"]
            last_result = SkillResult(
                status=SkillStatus(lr.get("status", "SUCCESS")),
                error_code=lr.get("error_code", ""),
                error_msg=lr.get("error_msg", ""),
                metrics=lr.get("metrics", {})
            )
        skills = SkillsState(registry=registry, running=running, last_result=last_result)
        
        react_d = d.get("react", {})
        decision = None
        if react_d.get("decision"):
            dec = react_d["decision"]
            decision = Decision(
                type=DecisionType(dec.get("type", "CONTINUE")),
                reason=dec.get("reason", ""),
                plan_patch=dec.get("plan_patch"),
                ops=dec.get("ops", [])
            )
        proposed_ops = None
        if react_d.get("proposed_ops"):
            po = react_d["proposed_ops"]
            proposed_ops = ProposedOps(
                to_cancel=po.get("to_cancel", []),
                to_dispatch=po.get("to_dispatch", []),
                to_speak=po.get("to_speak", []),
                need_approval=po.get("need_approval", False),
                approval_payload=po.get("approval_payload", {})
            )
        react = ReactState(
            iter=react_d.get("iter", 0),
            observation=react_d.get("observation", {}),
            decision=decision,
            proposed_ops=proposed_ops,
            stop_reason=react_d.get("stop_reason", "")
        )
        
        trace = TraceState(
            log=d.get("trace", {}).get("log", []),
            metrics=d.get("trace", {}).get("metrics", {})
        )
        
        return cls(
            messages=d.get("messages", []),
            hci=hci,
            world=world,
            robot=robot,
            tasks=tasks,
            skills=skills,
            react=react,
            trace=trace
        )
