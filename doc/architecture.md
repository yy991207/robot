# Robot Brain 项目架构文档

## 项目概述

Robot Brain 是一个基于 LangGraph 的机器人大脑调度系统，采用双环架构实现智能任务调度和执行。系统支持状态持久化、人机交互、技能管理等核心功能。

## 目录结构

```
robot_brain/
├── core/                    # 核心数据模型
│   ├── enums.py            # 枚举类型定义
│   ├── models.py           # 数据模型定义
│   ├── state.py            # 统一状态模型
│   └── __init__.py
├── service/                 # 服务层
│   ├── kernel/             # Kernel 外环服务
│   │   ├── base.py         # 节点基类接口
│   │   ├── hci_ingress.py  # 用户输入处理
│   │   ├── telemetry_sync.py # 遥测数据同步
│   │   ├── world_update.py # 世界模型更新
│   │   ├── event_arbitrate.py # 事件仲裁
│   │   ├── task_queue.py   # 任务队列管理
│   │   ├── kernel_route.py # 路由决策
│   │   └── __init__.py
│   ├── react/              # ReAct 内环服务
│   │   ├── base.py         # 节点基类接口
│   │   ├── build_observation.py # 观测构建
│   │   ├── react_decide.py # LLM 决策
│   │   ├── compile_ops.py  # 操作编译
│   │   ├── guardrails_check.py # 护栏检查
│   │   ├── human_approval.py # 人类审批
│   │   ├── dispatch_skills.py # 技能派发
│   │   ├── observe_result.py # 结果观察
│   │   ├── stop_or_loop.py # 循环控制
│   │   └── __init__.py
│   ├── skill/              # 技能服务
│   │   ├── registry.py     # 技能注册表
│   │   ├── executor.py     # 技能执行器
│   │   ├── skills/         # 具体技能实现
│   │   │   ├── navigate.py # 导航技能
│   │   │   ├── stop_base.py # 停止技能
│   │   │   └── speak.py    # 语音技能
│   │   └── __init__.py
│   └── __init__.py
├── graph/                   # LangGraph 图定义
│   ├── kernel_graph.py     # Kernel 外环图
│   ├── react_graph.py      # ReAct 内环图
│   └── __init__.py         # 主图组装
├── persistence/             # 持久化层
│   ├── checkpointer.py     # 检查点管理
│   └── __init__.py
├── main.py                  # 主入口
├── logging_config.py        # 日志配置
└── __init__.py
```

## 核心架构

### 双环调度架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Kernel 外环 (10Hz)                      │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │   K1    │→ │   K2    │→ │   K3    │→ │   K4    │        │
│  │HCI入口  │  │遥测同步 │  │世界更新 │  │事件仲裁 │        │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │
│       ↓                                       ↓             │
│  ┌─────────┐                            ┌─────────┐        │
│  │   K5    │←─────────────────────────← │   K6    │        │
│  │任务队列 │                            │  路由   │        │
│  └─────────┘                            └─────────┘        │
└─────────────────────────────────────────────────────────────┘
                              ↓ (EXEC 模式)
┌─────────────────────────────────────────────────────────────┐
│                      ReAct 内环                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │   R1    │→ │   R2    │→ │   R3    │→ │   R4    │        │
│  │构建观测 │  │LLM决策  │  │编译操作 │  │护栏检查 │        │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │
│       ↑                                       ↓             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │   R8    │← │   R7    │← │   R6    │← │   R5    │        │
│  │停止判断 │  │观察结果 │  │派发技能 │  │人类审批 │        │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### 运行模式

| 模式 | 说明 | 触发条件 |
|------|------|----------|
| IDLE | 空闲模式 | 无任务时 |
| EXEC | 执行模式 | 有任务待执行 |
| SAFE | 安全模式 | 检测到碰撞风险或电量极低 |
| CHARGE | 充电模式 | 电量低于阈值 |

## 核心组件

### 1. 状态模型 (BrainState)

统一状态树，包含以下子状态：
- HCIState: 人机交互状态
- WorldState: 世界模型状态
- RobotState: 机器人状态
- TasksState: 任务队列状态
- SkillsState: 技能执行状态
- ReactState: ReAct 循环状态
- TraceState: 追踪日志状态

### 2. Kernel 外环节点

| 节点 | 职责 |
|------|------|
| HCI_Ingress | 解析用户输入，识别 stop/pause/new_goal 指令 |
| Telemetry_Sync | 同步机器人遥测数据（位姿、速度、电量） |
| World_Update | 更新世界模型，生成环境摘要 |
| Event_Arbitrate | 事件检测与模式仲裁，处理抢占逻辑 |
| Task_Queue | 任务队列管理，优先级排序 |
| Kernel_Route | 根据模式决定路由目标 |

### 3. ReAct 内环节点

| 节点 | 职责 |
|------|------|
| Build_Observation | 压缩状态为结构化观测 |
| ReAct_Decide | LLM 决策，产出结构化决策 |
| Compile_Ops | 将决策编译为可执行操作 |
| Guardrails_Check | 技能验证、参数校验、资源冲突检测 |
| Human_Approval | 人类审批处理，支持 HITL |
| Dispatch_Skills | 技能派发和取消 |
| Observe_Result | 收集技能执行结果 |
| Stop_Or_Loop | 判断是否继续循环 |

### 4. 技能系统

- SkillRegistry: 技能注册表，管理技能定义
- SkillExecutor: 技能执行器接口
- 内置技能:
  - NavigateToPose: 导航到指定位姿
  - StopBase: 紧急停止
  - Speak: 语音输出

### 5. 持久化

- MemoryCheckpointer: 内存检查点存储
- FileCheckpointer: 文件检查点存储
- 支持状态快照、恢复、副作用幂等性

## 决策类型

| 类型 | 说明 |
|------|------|
| CONTINUE | 继续当前计划 |
| REPLAN | 重新规划 |
| RETRY | 重试当前操作 |
| SWITCH_TASK | 切换任务 |
| ASK_HUMAN | 请求人工干预 |
| FINISH | 任务完成 |
| ABORT | 中止任务 |

## 依赖

- langgraph >= 0.2.0
- langchain >= 0.2.0
- langchain-openai >= 0.1.0
- pydantic >= 2.0.0
- pytest >= 8.0.0
- hypothesis >= 6.0.0
