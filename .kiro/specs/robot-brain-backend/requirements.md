# Requirements Document

## Introduction

本文档定义了机器人大脑后端服务的需求规格。该服务实现 LangGraph + ReAct 调度闭环，包含外环 Kernel（硬规则仲裁 + 抢占）和内环 ReAct Controller（反馈→二次编排→再执行），支持持久化、可恢复执行和人类审批中断。

## Glossary

- **Kernel**: 外环调度内核，负责硬规则仲裁、模式切换和抢占决策
- **ReAct_Controller**: 内环控制器，实现 LLM 决策循环（Observation→Decision→Action）
- **State_Manager**: 状态管理器，维护统一数据模型
- **Skill_Executor**: 技能执行器，封装 ROS2 Action/Service 调用
- **HCI_Handler**: 人机交互处理器，处理用户输入和审批流程
- **Checkpointer**: 持久化组件，支持 durable execution
- **Mode**: 系统模式，包括 SAFE/CHARGE/EXEC/IDLE
- **Decision_Type**: LLM 决策类型，包括 CONTINUE/REPLAN/RETRY/SWITCH_TASK/ASK_HUMAN/FINISH/ABORT

## Requirements

### Requirement 1: 状态管理

**User Story:** As a 系统开发者, I want 统一的状态数据模型, so that 各组件可以共享和更新机器人状态。

#### Acceptance Criteria

1. THE State_Manager SHALL 维护 HCI 状态（user_utterance、user_interrupt、approval_response）
2. THE State_Manager SHALL 维护 World 状态（summary、zones、obstacles）
3. THE State_Manager SHALL 维护 Robot 状态（pose、twist、battery_pct、battery_state、resources、distance_to_target）
4. THE State_Manager SHALL 维护 Tasks 状态（inbox、queue、active_task_id、mode、preempt_flag）
5. THE State_Manager SHALL 维护 Skills 状态（registry、running、last_result）
6. THE State_Manager SHALL 维护 React 状态（iter、observation、decision、proposed_ops、stop_reason）
7. THE State_Manager SHALL 维护 Trace 状态（log、metrics）
8. WHEN 状态更新时, THE State_Manager SHALL 支持序列化为 JSON 格式

### Requirement 2: Kernel 外环调度

**User Story:** As a 机器人系统, I want 外环调度内核, so that 可以进行硬规则仲裁和抢占决策。

#### Acceptance Criteria

1. WHEN 接收用户输入时, THE Kernel SHALL 通过 HCI_Ingress 节点识别 stop/pause/new_goal 指令
2. WHEN 同步遥测数据时, THE Kernel SHALL 通过 Sim_Telemetry_Sync 节点更新机器人位姿、电量、忙闲状态
3. WHEN 更新世界模型时, THE Kernel SHALL 通过 World_Model_Update 节点生成世界摘要
4. WHEN 检测事件时, THE Kernel SHALL 通过 Event_Detect_And_Mode_Arbitrate 节点裁决系统模式（SAFE/CHARGE/EXEC/IDLE）
5. WHEN 更新任务队列时, THE Kernel SHALL 通过 Task_Queue_Update 节点将用户目标转为结构化任务
6. WHEN 路由决策时, THE Kernel SHALL 通过 Kernel_Route 节点根据 mode 路由到对应处理流程
7. IF 检测到安全事件, THEN THE Kernel SHALL 立即切换到 SAFE 模式并抢占当前任务
8. IF 电量低于阈值, THEN THE Kernel SHALL 切换到 CHARGE 模式

### Requirement 3: ReAct 内环控制

**User Story:** As a 机器人系统, I want ReAct 内环控制器, so that LLM 可以基于反馈进行二次编排和再执行。

#### Acceptance Criteria

1. WHEN 构建观测时, THE ReAct_Controller SHALL 通过 Build_Observation 节点压缩世界和机器人状态为结构化 observation
2. WHEN LLM 决策时, THE ReAct_Controller SHALL 通过 ReAct_Decide 节点产出结构化决策（type、reason、plan_patch、ops）
3. WHEN 编译操作时, THE ReAct_Controller SHALL 通过 Compile_Ops_From_Decision 节点将决策编译为可执行操作
4. WHEN 检查护栏时, THE ReAct_Controller SHALL 通过 Guardrails_And_Resource_Check 节点验证技能存在性、参数正确性、资源冲突
5. WHEN 需要审批时, THE ReAct_Controller SHALL 通过 Human_Approval_Interrupt 节点触发 interrupt 暂停
6. WHEN 派发技能时, THE ReAct_Controller SHALL 通过 Dispatch_Skills 节点执行取消/派发操作
7. WHEN 观察执行结果时, THE ReAct_Controller SHALL 通过 Observe_Execution_Result 节点收集技能 feedback/result
8. WHEN 判断停止条件时, THE ReAct_Controller SHALL 通过 ReAct_Stop_Or_Loop 节点决定继续循环或退出
9. THE ReAct_Controller SHALL 支持 LLM 决策类型：CONTINUE、REPLAN、RETRY、SWITCH_TASK、ASK_HUMAN、FINISH、ABORT

### Requirement 4: 技能执行

**User Story:** As a 机器人系统, I want 技能执行器, so that 可以调用、取消和监控 ROS2 技能。

#### Acceptance Criteria

1. THE Skill_Executor SHALL 维护技能注册表（name、interface_type、args_schema、resources_required、preemptible、cancel_supported、timeout_s、error_map）
2. WHEN 派发技能时, THE Skill_Executor SHALL 调用对应的 ROS2 Action/Service
3. WHEN 取消技能时, THE Skill_Executor SHALL 发送取消请求并等待确认
4. WHEN 技能执行中, THE Skill_Executor SHALL 持续收集 feedback 并更新 running 状态
5. WHEN 技能完成时, THE Skill_Executor SHALL 记录 last_result（status、error_code、error_msg、metrics）
6. THE Skill_Executor SHALL 支持 NavigateToPose 技能（长时导航动作）
7. THE Skill_Executor SHALL 支持 StopBase 技能（高优停止动作）
8. THE Skill_Executor SHALL 支持 Speak/Notify 技能（用户通知）

### Requirement 5: 持久化与恢复

**User Story:** As a 系统运维人员, I want 持久化和恢复能力, so that 系统中断后可以恢复执行。

#### Acceptance Criteria

1. THE Checkpointer SHALL 在每个节点执行后保存状态快照
2. WHEN 恢复执行时, THE Checkpointer SHALL 根据 thread_id 加载对应的状态快照
3. THE Checkpointer SHALL 确保副作用操作（Dispatch_Skills）不会在恢复时重复执行
4. WHEN 序列化状态时, THE Checkpointer SHALL 将状态转换为 JSON 格式存储
5. WHEN 反序列化状态时, THE Checkpointer SHALL 从 JSON 格式恢复状态对象

### Requirement 6: 人机交互与审批

**User Story:** As a 操作员, I want 人机交互和审批机制, so that 可以在关键动作前进行审批或编辑。

#### Acceptance Criteria

1. WHEN 接收用户输入时, THE HCI_Handler SHALL 解析用户意图（stop/pause/new_goal/normal）
2. WHEN 需要审批时, THE HCI_Handler SHALL 触发 interrupt 并暂停执行
3. WHEN 用户响应审批时, THE HCI_Handler SHALL 处理 approve/edit/reject 响应
4. IF 用户 approve, THEN THE HCI_Handler SHALL 继续执行原计划
5. IF 用户 edit, THEN THE HCI_Handler SHALL 使用编辑后的参数继续执行
6. IF 用户 reject, THEN THE HCI_Handler SHALL 取消当前操作并通知 ReAct_Controller

### Requirement 7: 优先级与抢占

**User Story:** As a 机器人系统, I want 优先级和抢占机制, so that 高优任务可以打断低优任务。

#### Acceptance Criteria

1. THE Kernel SHALL 按优先级排序：安全事件 > 电量低 > 用户打断 > 主任务 > 后台任务
2. WHEN SAFE 模式触发时, THE Kernel SHALL 立即抢占任何正在执行的任务
3. WHEN CHARGE 模式触发时, THE Kernel SHALL 抢占主任务并转入充电流程
4. WHEN 用户发出 stop 指令时, THE Kernel SHALL 取消当前任务
5. WHEN 用户发出新目标时, THE Kernel SHALL 根据优先级决定是否抢占当前任务
6. THE Kernel SHALL 维护资源模型（base、arm、gripper）防止资源冲突

### Requirement 8: 可观测性

**User Story:** As a 开发者, I want 可观测性支持, so that 可以监控和调试系统运行状态。

#### Acceptance Criteria

1. THE State_Manager SHALL 支持 streaming 输出状态更新
2. THE Kernel SHALL 在 trace.log 中记录仲裁决策和原因
3. THE ReAct_Controller SHALL 在 trace.log 中记录 LLM 决策和原因
4. THE Skill_Executor SHALL 在 trace.log 中记录技能派发和结果
5. WHEN 发生错误时, THE State_Manager SHALL 记录错误详情到 trace.log
