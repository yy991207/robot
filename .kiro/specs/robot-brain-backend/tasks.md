# Implementation Plan: Robot Brain Backend

## Overview

本实现计划将设计文档转化为可执行的编码任务。采用自底向上的方式：先实现核心数据模型，再实现各层服务，最后组装 LangGraph 图。

## Tasks

- [x] 1. 项目初始化和核心数据模型
  - [x] 1.1 创建项目目录结构和依赖配置
    - 创建 robot_brain/ 目录结构（core/service/graph/persistence）
    - 创建 pyproject.toml 或 requirements.txt
    - 配置 pytest 和 hypothesis
    - _Requirements: 项目基础设施_

  - [x] 1.2 实现核心枚举类型 (core/enums.py)
    - 实现 Mode、DecisionType、UserInterruptType、ApprovalAction 枚举
    - _Requirements: 1.4, 3.9_

  - [x] 1.3 实现核心数据模型 (core/models.py)
    - 实现 Pose、Twist、Task、SkillDef、RunningSkill、SkillResult、Decision、ProposedOps 数据类
    - _Requirements: 1.1-1.7, 4.1_

  - [x] 1.4 实现统一状态模型 (core/state.py)
    - 实现 HCIState、WorldState、RobotState、TasksState、SkillsState、ReactState、TraceState
    - 实现 BrainState 主状态类
    - 实现 serialize/deserialize 方法
    - _Requirements: 1.1-1.8_

  - [x] 1.5 编写状态模型属性测试
    - **Property 1: 状态模型完整性**
    - **Property 2: 状态序列化 Round-Trip**
    - **Validates: Requirements 1.1-1.8, 5.4, 5.5**

- [x] 2. Checkpoint - 核心模型验证
  - 确保所有测试通过，如有问题请提出

- [x] 3. Kernel 外环服务实现
  - [x] 3.1 实现 HCI_Ingress 节点 (service/kernel/hci_ingress.py)
    - 实现用户输入解析
    - 识别 stop/pause/new_goal 指令
    - 更新 hci.user_utterance 和 hci.user_interrupt
    - _Requirements: 2.1, 6.1_

  - [x] 3.2 编写 HCI_Ingress 属性测试
    - **Property 3: 用户指令识别正确性**
    - **Validates: Requirements 2.1, 6.1**

  - [x] 3.3 实现 Telemetry_Sync 节点 (service/kernel/telemetry_sync.py)
    - 实现遥测数据同步接口
    - 更新 robot.pose/twist/battery_pct/battery_state/resources
    - _Requirements: 2.2_

  - [x] 3.4 实现 World_Update 节点 (service/kernel/world_update.py)
    - 实现世界模型更新
    - 生成 world.summary
    - _Requirements: 2.3_

  - [x] 3.5 实现 Event_Arbitrate 节点 (service/kernel/event_arbitrate.py)
    - 实现事件检测逻辑
    - 实现模式仲裁（SAFE/CHARGE/EXEC/IDLE）
    - 实现抢占决策
    - _Requirements: 2.4, 2.7, 2.8, 7.1-7.5_

  - [x] 3.6 编写 Event_Arbitrate 属性测试
    - **Property 4: 模式仲裁确定性**
    - **Property 5: 抢占规则一致性**
    - **Validates: Requirements 2.4, 2.7, 2.8, 7.1-7.5**

  - [x] 3.7 实现 Task_Queue 节点 (service/kernel/task_queue.py)
    - 实现任务队列管理
    - 实现用户目标到结构化任务的转换
    - 实现优先级排序
    - _Requirements: 2.5, 7.1_

  - [x] 3.8 实现 Kernel_Route 节点 (service/kernel/kernel_route.py)
    - 实现模式路由逻辑
    - _Requirements: 2.6_

- [x] 4. Checkpoint - Kernel 外环验证
  - 确保所有测试通过，如有问题请提出

- [x] 5. ReAct 内环服务实现
  - [x] 5.1 实现 Build_Observation 节点 (service/react/build_observation.py)
    - 压缩世界和机器人状态为结构化 observation
    - 更新 react.observation 和 messages
    - _Requirements: 3.1_

  - [x] 5.2 实现 ReAct_Decide 节点 (service/react/react_decide.py)
    - 实现 LLM 决策调用
    - 产出结构化决策（type、reason、plan_patch、ops）
    - _Requirements: 3.2, 3.9_

  - [x] 5.3 编写 ReAct_Decide 属性测试
    - **Property 7: 决策类型完备性**
    - **Validates: Requirements 3.2, 3.9**

  - [x] 5.4 实现 Compile_Ops 节点 (service/react/compile_ops.py)
    - 将决策编译为可执行操作
    - 生成 to_cancel、to_dispatch、to_speak、need_approval
    - _Requirements: 3.3_

  - [x] 5.5 实现 Guardrails_Check 节点 (service/react/guardrails_check.py)
    - 实现技能存在性检查
    - 实现参数 schema 验证
    - 实现资源冲突检测
    - _Requirements: 3.4, 7.6_

  - [x] 5.6 编写 Guardrails_Check 属性测试
    - **Property 6: 资源冲突检测**
    - **Validates: Requirements 3.4, 7.6**

  - [x] 5.7 实现 Human_Approval 节点 (service/react/human_approval.py)
    - 实现审批触发逻辑
    - 实现 interrupt 暂停
    - 实现审批响应处理
    - _Requirements: 3.5, 6.2-6.6_

  - [x] 5.8 编写 Human_Approval 属性测试
    - **Property 8: 审批响应处理正确性**
    - **Validates: Requirements 6.3-6.6**

  - [x] 5.9 实现 Dispatch_Skills 节点 (service/react/dispatch_skills.py)
    - 实现技能取消和派发
    - 更新 skills.running
    - _Requirements: 3.6_

  - [x] 5.10 实现 Observe_Result 节点 (service/react/observe_result.py)
    - 收集技能 feedback/result
    - 更新 skills.last_result
    - _Requirements: 3.7_

  - [x] 5.11 实现 Stop_Or_Loop 节点 (service/react/stop_or_loop.py)
    - 实现停止条件判断
    - 实现循环/退出决策
    - _Requirements: 3.8_

  - [x] 5.12 编写 Stop_Or_Loop 属性测试
    - **Property 9: 停止条件判断正确性**
    - **Validates: Requirements 3.8**

- [x] 6. Checkpoint - ReAct 内环验证
  - 确保所有测试通过，如有问题请提出

- [x] 7. 技能执行服务实现
  - [x] 7.1 实现技能注册表 (service/skill/registry.py)
    - 实现技能定义存储
    - 实现技能查询接口
    - _Requirements: 4.1_

  - [x] 7.2 编写技能注册表属性测试
    - **Property 10: 技能注册表完整性**
    - **Validates: Requirements 4.1**

  - [x] 7.3 实现技能执行器基类 (service/skill/executor.py)
    - 实现 ISkillExecutor 接口
    - 实现 dispatch/cancel/get_feedback/get_result 方法
    - _Requirements: 4.2-4.5_

  - [x] 7.4 实现 NavigateToPose 技能 (service/skill/skills/navigate.py)
    - 封装 Nav2 NavigateToPose Action
    - _Requirements: 4.6_

  - [x] 7.5 实现 StopBase 技能 (service/skill/skills/stop_base.py)
    - 实现紧急停止功能
    - _Requirements: 4.7_

  - [x] 7.6 实现 Speak 技能 (service/skill/skills/speak.py)
    - 实现用户通知功能
    - _Requirements: 4.8_

- [x] 8. Checkpoint - 技能服务验证
  - 确保所有测试通过，如有问题请提出

- [x] 9. LangGraph 图组装
  - [x] 9.1 实现 Kernel 外环图 (graph/kernel_graph.py)
    - 组装 K1-K6 节点
    - 配置节点间路由
    - _Requirements: 2.1-2.8_

  - [x] 9.2 实现 ReAct 内环图 (graph/react_graph.py)
    - 组装 R1-R8 节点
    - 配置循环和退出条件
    - _Requirements: 3.1-3.9_

  - [x] 9.3 实现 Checkpointer (persistence/checkpointer.py)
    - 实现状态快照保存
    - 实现状态恢复
    - 确保副作用幂等性
    - _Requirements: 5.1-5.3_

  - [x] 9.4 组装主图并配置持久化 (graph/__init__.py)
    - 连接 Kernel 和 ReAct 子图
    - 配置 checkpointer
    - 配置 interrupt 处理
    - _Requirements: 5.1-5.3, 6.2_

- [x] 10. 入口和集成
  - [x] 10.1 实现主入口 (main.py)
    - 初始化各组件
    - 配置 streaming 输出
    - _Requirements: 8.1_

  - [x] 10.2 实现日志记录
    - 配置 trace.log 记录
    - _Requirements: 8.2-8.5_

- [x] 11. Final Checkpoint - 完整系统验证
  - 确保所有测试通过
  - 验证端到端流程
  - 如有问题请提出

## Notes

- 每个任务都引用了具体的需求条款以便追溯
- Checkpoint 任务用于阶段性验证
- 属性测试验证通用正确性属性
- 单元测试验证具体示例和边界情况
- 所有任务都必须完成
