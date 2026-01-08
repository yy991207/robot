# Design Document: Robot Brain Backend

## Overview

本设计文档描述机器人大脑后端服务的架构设计。系统采用分层架构，核心是 LangGraph 实现的双环调度系统：外环 Kernel 负责硬规则仲裁和抢占决策，内环 ReAct Controller 负责 LLM 智能编排。

系统使用 Python 作为主要开发语言，基于 LangGraph 框架实现状态图和持久化执行，通过 ROS2 接口与机器人技能层交互。

## Architecture

```mermaid
graph TB
    subgraph "L4 持久化与HITL"
        CP[Checkpointer]
        INT[Interrupt Handler]
    end
    
    subgraph "L3 ReAct内环"
        R1[Build_Observation]
        R2[ReAct_Decide]
        R3[Compile_Ops]
        R4[Guardrails_Check]
        R5[Human_Approval]
        R6[Dispatch_Skills]
        R7[Observe_Result]
        R8[Stop_Or_Loop]
    end
    
    subgraph "L2 Kernel外环"
        K1[HCI_Ingress]
        K2[Telemetry_Sync]
        K3[World_Update]
        K4[Event_Arbitrate]
        K5[Task_Queue]
        K6[Kernel_Route]
    end
    
    subgraph "L1 技能层"
        SE[Skill_Executor]
        NAV[NavigateToPose]
        STOP[StopBase]
        SPEAK[Speak/Notify]
    end
    
    K1 --> K2 --> K3 --> K4 --> K5 --> K6
    K6 -->|EXEC| R1
    R1 --> R2 --> R3 --> R4 --> R5 --> R6 --> R7 --> R8
    R8 -->|LOOP| R1
    R8 -->|EXIT| K1
    R6 --> SE
    SE --> NAV
    SE --> STOP
    SE --> SPEAK


## Components and Interfaces

### 目录结构

```
robot_brain/
├── core/                      # 核心领域模型
│   ├── __init__.py
│   ├── state.py              # 统一状态模型
│   ├── models.py             # 数据模型定义
│   └── enums.py              # 枚举类型
├── service/                   # 业务服务层
│   ├── __init__.py
│   ├── kernel/               # Kernel外环服务
│   │   ├── __init__.py
│   │   ├── hci_ingress.py
│   │   ├── telemetry_sync.py
│   │   ├── world_update.py
│   │   ├── event_arbitrate.py
│   │   ├── task_queue.py
│   │   └── kernel_route.py
│   ├── react/                # ReAct内环服务
│   │   ├── __init__.py
│   │   ├── build_observation.py
│   │   ├── react_decide.py
│   │   ├── compile_ops.py
│   │   ├── guardrails_check.py
│   │   ├── human_approval.py
│   │   ├── dispatch_skills.py
│   │   ├── observe_result.py
│   │   └── stop_or_loop.py
│   └── skill/                # 技能执行服务
│       ├── __init__.py
│       ├── executor.py
│       ├── registry.py
│       └── skills/
│           ├── navigate.py
│           ├── stop_base.py
│           └── speak.py
├── graph/                     # LangGraph图定义
│   ├── __init__.py
│   ├── kernel_graph.py
│   └── react_graph.py
├── persistence/               # 持久化层
│   ├── __init__.py
│   └── checkpointer.py
└── main.py                    # 入口
```

### 核心接口定义

#### IStateManager (状态管理接口)

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class IStateManager(ABC):
    @abstractmethod
    def get_state(self) -> "BrainState":
        """获取当前状态"""
        pass
    
    @abstractmethod
    def update_state(self, updates: Dict[str, Any]) -> "BrainState":
        """更新状态"""
        pass
    
    @abstractmethod
    def serialize(self) -> str:
        """序列化为JSON"""
        pass
    
    @abstractmethod
    def deserialize(self, data: str) -> "BrainState":
        """从JSON反序列化"""
        pass
```

#### ISkillExecutor (技能执行接口)

```python
class ISkillExecutor(ABC):
    @abstractmethod
    async def dispatch(self, skill_name: str, params: Dict[str, Any]) -> str:
        """派发技能，返回goal_id"""
        pass
    
    @abstractmethod
    async def cancel(self, goal_id: str) -> bool:
        """取消技能"""
        pass
    
    @abstractmethod
    async def get_feedback(self, goal_id: str) -> Dict[str, Any]:
        """获取执行反馈"""
        pass
    
    @abstractmethod
    async def get_result(self, goal_id: str) -> Dict[str, Any]:
        """获取执行结果"""
        pass
```

#### IKernelNode (Kernel节点接口)

```python
class IKernelNode(ABC):
    @abstractmethod
    def execute(self, state: "BrainState") -> "BrainState":
        """执行节点逻辑"""
        pass
```

#### IReActNode (ReAct节点接口)

```python
class IReActNode(ABC):
    @abstractmethod
    async def execute(self, state: "BrainState") -> "BrainState":
        """执行节点逻辑（支持异步）"""
        pass
```


## Data Models

### BrainState (统一状态模型)

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum

class Mode(Enum):
    SAFE = "SAFE"
    CHARGE = "CHARGE"
    EXEC = "EXEC"
    IDLE = "IDLE"

class DecisionType(Enum):
    CONTINUE = "CONTINUE"
    REPLAN = "REPLAN"
    RETRY = "RETRY"
    SWITCH_TASK = "SWITCH_TASK"
    ASK_HUMAN = "ASK_HUMAN"
    FINISH = "FINISH"
    ABORT = "ABORT"

class UserInterruptType(Enum):
    NONE = "NONE"
    PAUSE = "PAUSE"
    STOP = "STOP"
    NEW_GOAL = "NEW_GOAL"

class ApprovalAction(Enum):
    APPROVE = "APPROVE"
    EDIT = "EDIT"
    REJECT = "REJECT"

@dataclass
class HCIState:
    user_utterance: str = ""
    user_interrupt: UserInterruptType = UserInterruptType.NONE
    interrupt_payload: Dict[str, Any] = field(default_factory=dict)
    approval_response: Optional[Dict[str, Any]] = None

@dataclass
class WorldState:
    summary: str = ""
    zones: List[str] = field(default_factory=list)
    obstacles: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class Pose:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    orientation_w: float = 1.0

@dataclass
class Twist:
    linear_x: float = 0.0
    angular_z: float = 0.0

@dataclass
class RobotState:
    pose: Pose = field(default_factory=Pose)
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
class Task:
    task_id: str
    goal: str
    priority: int = 0
    deadline: Optional[float] = None
    resources_required: List[str] = field(default_factory=list)
    preemptible: bool = True
    status: str = "PENDING"

@dataclass
class TasksState:
    inbox: List[Dict[str, Any]] = field(default_factory=list)
    queue: List[Task] = field(default_factory=list)
    active_task_id: Optional[str] = None
    mode: Mode = Mode.IDLE
    preempt_flag: bool = False
    preempt_reason: str = ""

@dataclass
class SkillDef:
    name: str
    interface_type: str  # ros2_action | ros2_service | internal
    args_schema: Dict[str, Any] = field(default_factory=dict)
    resources_required: List[str] = field(default_factory=list)
    preemptible: bool = True
    cancel_supported: bool = True
    timeout_s: float = 60.0
    error_map: Dict[str, str] = field(default_factory=dict)

@dataclass
class RunningSkill:
    goal_id: str
    skill_name: str
    start_time: float
    timeout_s: float
    resources_occupied: List[str] = field(default_factory=list)

@dataclass
class SkillResult:
    status: str  # SUCCESS | FAILED | CANCELLED
    error_code: str = ""
    error_msg: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SkillsState:
    registry: Dict[str, SkillDef] = field(default_factory=dict)
    running: List[RunningSkill] = field(default_factory=list)
    last_result: Optional[SkillResult] = None

@dataclass
class Decision:
    type: DecisionType = DecisionType.CONTINUE
    reason: str = ""
    plan_patch: Optional[Dict[str, Any]] = None
    ops: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class ProposedOps:
    to_cancel: List[str] = field(default_factory=list)
    to_dispatch: List[Dict[str, Any]] = field(default_factory=list)
    to_speak: List[str] = field(default_factory=list)
    need_approval: bool = False
    approval_payload: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ReactState:
    iter: int = 0
    observation: Dict[str, Any] = field(default_factory=dict)
    decision: Optional[Decision] = None
    proposed_ops: Optional[ProposedOps] = None
    stop_reason: str = ""

@dataclass
class TraceState:
    log: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BrainState:
    messages: List[Dict[str, Any]] = field(default_factory=list)
    hci: HCIState = field(default_factory=HCIState)
    world: WorldState = field(default_factory=WorldState)
    robot: RobotState = field(default_factory=RobotState)
    tasks: TasksState = field(default_factory=TasksState)
    skills: SkillsState = field(default_factory=SkillsState)
    react: ReactState = field(default_factory=ReactState)
    trace: TraceState = field(default_factory=TraceState)
```


## Correctness Properties

正确性属性是系统在所有有效执行中都应保持为真的特征或行为。属性作为人类可读规格和机器可验证正确性保证之间的桥梁。

### Property 1: 状态模型完整性

*For any* BrainState 对象，它必须包含所有必需的子状态（hci、world、robot、tasks、skills、react、trace），且每个子状态的必需字段都存在且类型正确。

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7**

### Property 2: 状态序列化 Round-Trip

*For any* 有效的 BrainState 对象，序列化为 JSON 后再反序列化，应得到与原对象等价的状态。

**Validates: Requirements 1.8, 5.4, 5.5**

### Property 3: 用户指令识别正确性

*For any* 用户输入字符串，HCI_Ingress 节点应正确识别其意图类型（stop/pause/new_goal/normal），且识别结果与输入内容语义一致。

**Validates: Requirements 2.1, 6.1**

### Property 4: 模式仲裁确定性

*For any* 给定的机器人状态（电量、安全事件、用户中断），Event_Detect_And_Mode_Arbitrate 节点应产出确定的模式（SAFE/CHARGE/EXEC/IDLE），且优先级顺序为：安全事件 > 电量低 > 用户打断 > 正常执行。

**Validates: Requirements 2.4, 2.7, 2.8, 7.1**

### Property 5: 抢占规则一致性

*For any* 系统状态，当触发 SAFE 模式时必须抢占当前任务；当触发 CHARGE 模式时必须抢占主任务；用户 stop 指令必须取消当前任务。

**Validates: Requirements 7.2, 7.3, 7.4, 7.5**

### Property 6: 资源冲突检测

*For any* 技能派发请求，如果请求的资源与当前运行技能占用的资源冲突，Guardrails_And_Resource_Check 节点应拒绝该请求。

**Validates: Requirements 3.4, 7.6**

### Property 7: 决策类型完备性

*For any* ReAct_Decide 节点的输出，其决策类型必须是 CONTINUE、REPLAN、RETRY、SWITCH_TASK、ASK_HUMAN、FINISH、ABORT 之一。

**Validates: Requirements 3.2, 3.9**

### Property 8: 审批响应处理正确性

*For any* 审批响应（approve/edit/reject），系统应正确处理：approve 继续原计划，edit 使用编辑后参数，reject 取消操作。

**Validates: Requirements 6.3, 6.4, 6.5, 6.6**

### Property 9: 停止条件判断正确性

*For any* ReAct 循环状态，当达成目标时应返回 FINISH，当迭代超限或连续失败时应返回 ASK_HUMAN 或 ABORT。

**Validates: Requirements 3.8**

### Property 10: 技能注册表完整性

*For any* 注册的技能，必须包含 name、interface_type、args_schema、resources_required、preemptible、cancel_supported、timeout_s、error_map 字段。

**Validates: Requirements 4.1**

## Error Handling

### 错误分类

1. **可恢复错误**：技能执行失败、网络超时、资源暂时不可用
   - 处理策略：RETRY 或 REPLAN

2. **需人工干预错误**：连续失败、参数无效、权限不足
   - 处理策略：ASK_HUMAN

3. **致命错误**：安全事件、系统异常
   - 处理策略：ABORT 并切换到 SAFE 模式

### 错误码映射

```python
ERROR_MAP = {
    "NAV_GOAL_REJECTED": "REPLAN",      # 目标点不可达，重新规划
    "NAV_TIMEOUT": "RETRY",              # 导航超时，重试
    "NAV_BLOCKED": "REPLAN",             # 路径被阻塞，重新规划
    "SKILL_NOT_FOUND": "ASK_HUMAN",      # 技能不存在，求助
    "RESOURCE_CONFLICT": "RETRY",        # 资源冲突，等待重试
    "PARAM_INVALID": "ASK_HUMAN",        # 参数无效，求助
    "SAFETY_VIOLATION": "ABORT",         # 安全违规，中止
    "BATTERY_CRITICAL": "ABORT",         # 电量危急，中止
}
```

## Testing Strategy

### 单元测试

- 测试各节点的独立逻辑
- 测试数据模型的序列化/反序列化
- 测试状态转换的正确性

### 属性测试

使用 Hypothesis 库进行属性测试，每个属性测试至少运行 100 次迭代。

```python
# 测试框架配置
import hypothesis
from hypothesis import given, settings, strategies as st

@settings(max_examples=100)
@given(state=brain_state_strategy())
def test_state_serialization_roundtrip(state):
    """Property 2: 状态序列化 Round-Trip"""
    serialized = state.serialize()
    deserialized = BrainState.deserialize(serialized)
    assert state == deserialized
```

### 集成测试

- 测试 Kernel 外环完整流程
- 测试 ReAct 内环完整流程
- 测试持久化和恢复功能
- 测试人机交互审批流程
