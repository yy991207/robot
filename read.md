# 机器人大脑 Demo（LangGraph + ReAct 调度闭环）Agent 开发文档（Linux 仿真版）

> 目标：在 **Linux** 上用 **物理仿真（Gazebo）**产生“世界状态 + 机器人客观状态（电量/忙闲/距离/执行进度）”，通过 **真实人机交互（HCI）**与 **真实 LLM**做 **ReAct（反馈→二次编排→再执行）**，实现可解释、可抢占、可恢复的任务调度 Demo。  
> 关键词：**外环内核（Kernel）硬抢占 + 内环 ReAct 智能编排**、**持久化可恢复执行**、**人类审批 interrupt**、**技能层（ROS2 Action）工业化兜底（Nav2 BT）**。

---

## 1. Demo 的范围定义

### 1.1 必须达成（MVP）
1) **物理仿真**：Gazebo 中机器人可运动，环境中有目标区域（厨房/客厅等）。  
2) **客观状态**：持续获得机器人位姿、到目标距离、当前是否忙闲、电量（仿真电池）。  
3) **技能执行**：至少一个长时技能（推荐：导航 NavigateToPose）+ 一个高优技能（Stop/E-Stop 语义）。  
4) **ReAct 闭环**：LLM 每一轮看到“执行反馈/世界变化”，决定是否 **继续 / 重试 / 改计划（replan）/ 求助（human）/ 结束**，并再次派发动作（循环直到停止条件）。  
5) **调度特性**：支持优先级（安全/电量/用户打断/主任务），支持抢占（取消正在跑的技能），支持恢复（失败后 retry/replan）。  
6) **HITL（可选但强烈推荐）**：关键动作前允许“审批/编辑/拒绝”，用 LangGraph interrupt 暂停并用 Command 恢复。  
7) **可观测**：图执行过程流式输出（state updates + LLM tokens + debug），用于 UI/日志。  

### 1.2 不做/延后（建议）
- 复杂 manipulation（抓取/开门）可延后；先把“调度闭环”跑稳。
- 低层控制实时性（RT 控制环）不在 LangGraph/LLM 内实现，确保安全链路独立。

---

## 2. 系统架构（分层与职责）

### 2.1 L0 安全与实时层（不依赖 LLM）
**职责**：急停/避障/限速/watchdog 等硬约束。  
> 注：ROS2 Executor 对实时/确定性并不天然友好，官方文档明确提到调度语义复杂、可能优先级反转、缺乏对回调执行顺序的显式控制；并说明在负载下可能变成 round-robin 而非 FIFO。  
**落地建议**：安全相关回调（控制环/安全监测）用 callback group 分离、独立 executor，并用 OS 线程调度优先级保障。官方 executor 文档也明确提到可把 callback group 分配给不同 executor，并通过 OS 调度配置优先级。  

### 2.2 L1 技能层（ROS2 Action/Service：工业化兜底）
**职责**：把机器人能力封装成“可调用、可取消、可反馈”的技能。  
- 推荐导航用 **Nav2**：其 BT Navigator 提供基于行为树的导航动作接口与 recovery 机制。  
- `NavigateToPose` Action 支持传入 `behavior_tree` 字段选择自定义 BT XML（为空则用默认带恢复的树）。  

### 2.3 L2 调度内核（Kernel 外环：硬规则仲裁 + 抢占）
**职责**：不让 LLM 决定“能不能做”，而是决定“当前系统模式”：  
- `SAFE`：安全覆盖（取消动作/停车）  
- `CHARGE`：电量低（转充电任务）  
- `EXEC`：正常执行（进入 ReAct 内环）  
- `IDLE`：等待用户  

### 2.4 L3 ReAct 内环（LangGraph 子图：反馈→二次编排→再执行）
**职责**：LLM 每轮根据观测（Observation）产出结构化决策（Decision），并派发下一步动作（Action），直到停止。  
- 可用自定义 LangGraph StateGraph 实现 ReAct loop；也可以参考 LangGraph/ LangChain 的 agent 工具（注意：LangGraph v1 文档提到 `create_react_agent` 的弃用/迁移方向，推荐使用新的 `create_agent` 路线或自建图）。  

### 2.5 L4 持久化与 HITL（LangGraph Durable Execution）
LangGraph 文档明确：启用 checkpointer 即拥有 durable execution；恢复执行需要指定 `thread_id`；并建议把有副作用/非确定性操作包装为 task，避免恢复时重复执行。  
Interrupt 文档也强调：`thread_id` 是“持久游标”，复用它会恢复同一线程；interrupt payload 会出现在 `__interrupt__` 供外部系统处理。  

---

## 3. 技术栈与依赖（建议组合）

### 3.1 Linux & ROS2 & 仿真
- Ubuntu + ROS 2（建议用你现有团队熟悉的发行版：Humble/Iron/Jazzy 等）
- Gazebo（Classic 或 Gazebo Sim / Ignition 体系均可）
- Nav2（导航栈 + BT Navigator）  

### 3.2 电量仿真
两条路线选其一：
1) Gazebo Sim 自带 Battery/Recharge 接口（仿真电池与充电服务）。  
2) Gazebo Classic + ROS 电池插件：例如 `gazebo_ros_battery` 可发布 `<robotNamespace>/battery_state (sensor_msgs/BatteryState)`，并更新荷电状态。  

### 3.3 LangGraph 能力点（你 Demo 需要用到的）
- durable execution（checkpointer + thread_id + task 包裹副作用）  
- interrupts（HITL：interrupt 暂停 + Command(resume=...) 恢复）  
- streaming（`values/updates/messages/debug/custom`）  

---

## 4. 统一数据模型（State Schema）

> 原则：LLM 不应直接吃“原始点云/全量 topic”，而吃 **摘要**；同时调度与恢复需要结构化字段（任务、资源、技能状态、失败码）。

### 4.1 State 顶层字段（建议）
- `messages`: LLM 上下文（用户话、系统提示、observation、tool result）
- `hci`:
  - `user_utterance`: 最新用户输入（str）
  - `user_interrupt`: `NONE|PAUSE|STOP|NEW_GOAL` + payload
  - `approval_response`: HITL 恢复输入（approve/edit/reject + edit payload）
- `world`:
  - `summary`: 世界摘要（str 或结构体）
  - `zones`: 语义区域（kitchen/living_room…）
  - `obstacles`: （可选）动态障碍摘要
- `robot`:
  - `pose`, `twist`
  - `battery_pct`, `battery_state`
  - `resources`: `{base_busy, arm_busy, gripper_busy, gpu_busy...}`
  - `distance_to_target`: 当前任务目标距离（float）
- `tasks`:
  - `inbox`: 新目标列表（结构化 goal）
  - `queue`: 任务队列（含 priority/deadline/resources/preemptible）
  - `active_task_id`
  - `mode`: `SAFE|CHARGE|EXEC|IDLE`
  - `preempt_flag`: 是否抢占当前任务
- `skills`:
  - `registry`: 技能清单（schema、资源、可取消、超时、失败码映射）
  - `running`: 当前运行中的技能（action goal id、开始时间、timeout、占用资源）
  - `last_result`: 最近技能结果（success/fail + error_code + metrics）
- `react`（ReAct 内环专用）:
  - `iter`: 迭代次数
  - `observation`: 结构化观测
  - `decision`: LLM 的结构化决策
  - `proposed_ops`: 编译后的操作（cancel/dispatch/speak/need_approval）
  - `stop_reason`: done/need_human/impossible/safety_override
- `trace`:
  - `log`: 决策日志（解释性）
  - `metrics`:（耗时/失败次数/重规划次数等）

---

## 5. 技能层（Skills）规范（必须“可取消、可反馈、可幂等”）

### 5.1 必须实现的技能（MVP）
1) `NavigateToPose`（长时动作）：用 Nav2 `nav2_msgs/action/NavigateToPose`。Goal 字段包含 `pose` 与可选 `behavior_tree`。  
2) `StopBase`（高优动作）：取消导航并停止底盘（可用 Nav2 cancel + 速度置零）。  
3) （推荐）`DockToCharger`：充电对接（可先用“导航到充电点 + 开始充电服务”的简化版）。Gazebo Sim 支持 battery recharge start/stop。  
4) `Speak/Notify`：对用户输出解释/状态（文本即可；语音可后加）。  

### 5.2 registry 中每个技能建议字段
- `name`
- `interface_type`: `ros2_action|ros2_service|internal`
- `args_schema`: 结构化参数（便于 LLM 输出 JSON）
- `resources_required`: 例如 `["base"]`
- `preemptible`: 是否允许抢占
- `cancel_supported`: 是否支持取消
- `timeout_s`
- `success_criteria`
- `error_map`: error_code → 可恢复建议（retry/replan/ask_human）

---

## 6. 行为树/状态机兜底（给“技能内部”用，不放到 LLM）
### 6.1 导航兜底：Nav2 BT
Nav2 文档给出 BT 结构例子（ComputePathToPose + FollowPath + 控制器节点等），并强调可配置 recovery、重试、subtree 等。  
这正是“LLM 给目标，底层稳定执行”的工业化路径。

### 6.2 行为树中的“优先级/抢占”语义（理解很关键）
BehaviorTree.CPP 文档明确：Fallback 家族在其他框架也叫 Selector/Priority；ReactiveFallback 用于当高优条件从 FAILURE→SUCCESS 时中断正在 RUNNING 的异步子节点。  
同时，异步 Action 需要返回 RUNNING 并实现 halt 以支持被中断。  

---

## 7. LangGraph 图设计（节点级规格）

### 7.1 总体：外环 Kernel + 内环 ReAct 子图
- Kernel：同步→事件检测→模式仲裁→任务队列更新→路由
- ReAct：Observation→LLM 决策→编译→护栏/资源→审批→派发→反馈→循环

---

# 7A. Kernel（外环）节点

## K1 `HCI_Ingress`
**职责**：接收真实用户输入；识别 stop/pause/new goal。  
**输入**：HCI 通道（CLI/Web/语音转写）；`tasks.active_task_id`（用于 stop 当前任务）。  
**输出**：
- 写 `hci.user_utterance`
- 写 `hci.user_interrupt`

**副作用**：无（只读输入）。

---

## K2 `Sim_Telemetry_Sync`
**职责**：从 ROS2/仿真同步客观状态：位姿、电量、忙闲、距离。  
**输入**：ROS2 topics/actions；`skills.running`、`tasks.active_task_id`。  
**输出**：
- 更新 `robot.pose/twist`
- 更新 `robot.battery_pct/battery_state`
- 更新 `robot.resources`
- 更新 `robot.distance_to_target`

**副作用**：无（只读）。

---

## K3 `World_Model_Update`
**职责**：更新世界摘要（给 LLM 与仲裁用）。  
**输入**：仿真传感器或仿真假值；上一轮 `world`。  
**输出**：
- 更新 `world.summary`（建议结构化：可达性/障碍/目标区状态）

**副作用**：无。

---

## K4 `Event_Detect_And_Mode_Arbitrate`
**职责**：检测事件并裁决模式（SAFE/CHARGE/EXEC/IDLE），决定是否抢占。  
**输入**：`robot.*`、`world.*`、`hci.user_interrupt`、`skills.running`。  
**输出**：
- `tasks.mode`
- `tasks.preempt_flag`（含原因：SAFETY/BATTERY/USER）
- `trace.log += 仲裁解释`

**副作用**：无（只做决定）。

---

## K5 `Task_Queue_Update`
**职责**：把用户话/新目标转成结构化任务，更新队列与优先级。  
**输入**：`hci.user_utterance`、`tasks.inbox`、`skills.registry`、策略。  
**输出**：
- `tasks.queue`（push/merge）
- `tasks.active_task_id`（必要时插队）

**副作用**：无。

---

## K6 `Kernel_Route`
**职责**：路由到：
- SAFE：进入安全动作（直接取消/Stop）
- CHARGE：进入充电任务 ReAct
- EXEC：进入正常 ReAct
- IDLE：等待下一次 tick / 继续 HCI

**输入**：`tasks.mode`  
**输出**：路由决策（通常只影响下一节点）。

---

# 7B. ReAct Controller（内环）子图节点

## R1 `Build_Observation`
**职责**：把“世界+机器人客观状态+任务+技能结果”压缩成结构化 observation；写入 messages。  
**输入**：
- `world.summary`
- `robot.pose/battery_pct/resources/distance_to_target`
- `tasks.active_task_id` 与该任务元信息
- `skills.running`
- `skills.last_result`
**输出**：
- `react.observation`（结构化）
- `messages += observation`
- `react.iter += 1`

**副作用**：无。

---

## R2 `ReAct_Decide`（LLM 决策节点：二次编排发生处）
**职责**：LLM 基于 observation 产出结构化决策（继续/重试/改编排/切任务/求助/结束）。  
**输入**：
- `messages`（含 observation 与历史工具结果）
- `skills.registry`
- `tasks.queue` 与 active task
**输出**（建议强制 JSON 结构）：
- `react.decision`，示例字段：
  - `type`: `CONTINUE | REPLAN | RETRY | SWITCH_TASK | ASK_HUMAN | FINISH | ABORT`
  - `reason`
  - `plan_patch`（可选：改子目标/改约束/改顺序）
  - `ops`（可选：建议执行的动作集合：dispatch/cancel/speak/approval）
- `trace.log += LLM 决策解释`

**副作用**：无（只决策）。

> 说明：这就是你强调的“LLM 收到反馈后是否二次任务编排并再次执行”的逻辑核心。

---

## R3 `Compile_Ops_From_Decision`
**职责**：把 LLM 决策编译为可执行操作集合（取消哪些、执行哪些、是否说话、是否需要审批）。  
**输入**：`react.decision`、`skills.running`、`tasks.preempt_flag`、`robot.resources`。  
**输出**：
- `react.proposed_ops = {to_cancel, to_dispatch, to_speak, need_approval, approval_payload}`

**副作用**：无。

---

## R4 `Guardrails_And_Resource_Check`
**职责**：硬护栏与资源检查（LLM 说了不算）：
- 技能存在、参数 schema 正确
- 资源不冲突（base/arm 等互斥）
- 抢占是否允许
- 是否触发审批策略
**输入**：`react.proposed_ops`、`skills.registry`、`robot.resources`、`tasks.mode`。  
**输出**：
- `skills.to_cancel`
- `skills.to_dispatch`
- `hci.approval_required` + `approval_payload`（若需要）
- 若不通过：写 `skills.last_result`（作为“拒绝执行”的 tool result），并把 `react.decision.type` 改为 `REPLAN` 或 `ASK_HUMAN`

**副作用**：无。

---

## R5 `Human_Approval_Interrupt`（可选但推荐）
**职责**：关键动作前暂停，等人类 approve/edit/reject。  
**输入**：`hci.approval_required`、`approval_payload`。  
**输出**：
- 暂停：触发 interrupt（外部拿到 `__interrupt__`）  
- 恢复：通过 `Command(resume=...)` 回填 `hci.approval_response`，并更新 `skills.to_dispatch`  

**副作用**：无（暂停/等待交互）。

---

## R6 `Dispatch_Skills`（唯一允许产生物理副作用的节点）
**职责**：执行取消/派发（ROS2 action/service 调用），记录 running handle。  
**输入**：`skills.to_cancel`、`skills.to_dispatch`。  
**输出**：
- 更新 `skills.running`
- `trace.log += dispatch 记录`

**副作用**：有（真正发导航目标/取消/停车等）。

> durable execution 设计要点：LangGraph 建议把“有副作用的操作”包在 task 里，避免恢复后重复调用；并保证工作流幂等/确定性。  

---

## R7 `Observe_Execution_Result`
**职责**：收集技能 feedback/result，结构化写回，作为下一轮 observation 的关键输入。  
**输入**：ROS2 action feedback/result；`skills.running`。  
**输出**：
- 更新 `skills.running`（done/failed）
- `skills.last_result = {status, error_code, error_msg, metrics(distance_remaining/eta/…)}`
- `messages += tool_result`

> 例如 Nav2 NavigateToPose action 会反馈当前位姿、剩余距离等（不同发行版字段略有差异），并有 error_code/error_msg。  

**副作用**：无（只读结果）。

---

## R8 `ReAct_Stop_Or_Loop`
**职责**：判断停止条件或继续下一轮：
- 达成目标：FINISH
- 失败可恢复：回 R1（触发二次编排）
- 连续失败/迭代超限：ASK_HUMAN 或 ABORT
**输入**：`react.decision`、`skills.last_result`、`robot.distance_to_target`、`react.iter`、`tasks.mode`。  
**输出**：
- `react.stop_reason`
- 可能更新 `tasks.active_task_id`（切任务）或清理队列
- 路由：回 R1 或退出子图回 Kernel

**副作用**：无。

---

## 8. 调度策略（优先级/抢占/并行）

### 8.1 优先级来源（建议硬编码在 Kernel，而不是提示词）
从高到低（可按需调整）：
1) **安全事件**：碰撞风险/急停 → 立即抢占（cancel + stop）  
2) **电量低**：转 CHARGE（抢占主任务）  
3) **用户打断**：stop/pause/插队新目标  
4) **主任务**：用户当前指令  
5) **后台任务**：日志/解释/非关键感知  

### 8.2 资源模型（MVP 简化版）
- `base`：独占（导航/对接/停车）  
- `arm`、`gripper`：独占（如果你之后加操作）  
- `gpu`：配额（可先不做）  

并行规则：
- 允许 `Speak/Notify` 与 `Navigate` 并行（不抢 base）  
- 禁止两个 `base` 类技能并行  
- 若要并行监控：监控节点只读，不占用 base  

### 8.3 抢占规则（Preemption）
- `SAFE` 模式永远可抢占  
- `CHARGE` 可抢占主任务  
- 主任务抢占主任务：仅当新任务 priority 更高或用户明确要求  

---

## 9. LangGraph 持久化、恢复与幂等性规范（非常关键）

### 9.1 必须遵守
1) **启用 checkpointer**（否则无法 durable execution / interrupt 恢复）。  
2) 每次执行必须指定 `thread_id`（同一个 thread_id 才能恢复同一条执行线程）。  
3) **所有副作用调用（ROS2 发 goal、写文件、调用外部 API）都集中在 R6，并用 task 包裹**，保证恢复时不会重复执行同一副作用。  
4) 节点尽量“纯函数式”：同一输入 state 产生同一输出，便于回放与调试。

### 9.2 interrupt/HITL 规范
- interrupt 用于审批/编辑关键动作；恢复使用 `Command(resume=...)`。  
- 恢复后要把人类输入写回 `hci.approval_response`，并重新走 R4 校验（避免人类编辑引入非法参数）。

---

## 10. 可观测性与 UI（强烈建议做，不然 Demo “不像大脑”）

### 10.1 Streaming 输出
LangGraph 支持多种 stream_mode：  
- `values`：每步完整 state  
- `updates`：每步增量更新  
- `messages`：LLM token 流  
- `debug`：尽可能多的调试信息  
- `custom`：节点自定义事件  
  

### 10.2 UI 最小面板建议
- 当前 `tasks.mode`（SAFE/CHARGE/EXEC/IDLE）
- 当前 active task 与队列（优先级、deadline）
- `robot.battery_pct`、`distance_to_target`
- `skills.running`（goal_id、开始时间、超时）
- `react.iter` 与 `react.decision`（解释性文本）
- 最近一次失败码与恢复动作

---

## 11. 测试计划（用场景驱动，验证“二次编排”确实发生）

### 11.1 必测场景
1) **正常导航成功**：LLM 决策 CONTINUE→FINISH  
2) **导航失败/卡住**：LLM 观察到失败码/距离不变 → REPLAN（换目标点/等待/重试）→ 成功或求助  
3) **电量低抢占**：执行中电量跌破阈值 → Kernel 切 CHARGE → cancel 当前导航 → 去充电点  
4) **用户插队**：执行中用户发新目标 → queue 更新、优先级更高 → 抢占切换  
5) **需要审批的动作**：触发 interrupt → 人类 approve/edit → 继续执行并记录痕迹  
6) **进程中断恢复**：杀掉“大脑”进程 → 用同一 `thread_id` 恢复，继续执行（验证 durable execution）  

### 11.2 防死循环策略
- `react.iter` 上限（例如 20 轮）
- 连续失败计数（例如同一技能 3 次失败则 ASK_HUMAN/ABORT）
- “距离无进展”判定（N 秒内 distance_remaining 几乎不变 → 触发 REPLAN）

---

## 12. 关键实现注意事项（避免 Demo 翻车）

1) **不要把优先级调度只写在 Prompt 里**：安全/电量/用户打断必须在 Kernel（K4/K6）硬裁决。  
2) **ROS2 回调层面的优先级要工程化**：executor 文档指出负载下 round-robin、可能优先级反转、无显式回调顺序控制；需要 callback group + 多 executor + OS 线程优先级策略来保证关键链路。  
3) **副作用集中在 R6**：恢复/interrupt 才不会重复发 goal。durable execution 文档强调把副作用操作包裹在 task，并保证幂等/确定性。  
4) **导航兜底交给 Nav2 BT**：LLM 只给目标与策略，执行细节交给 BT Navigator（包含 recovery 与可配置 BT）。  
5) **理解“抢占”的代价**：行为树里 ReactiveFallback 可中断 RUNNING 子节点，但前提是异步 Action 支持 halt/清理。  

---

## 13. 交付物清单（你最终应该“做出来”的东西）

### 13.1 仿真侧
- Gazebo world：含语义区域/目标点/障碍物
- 机器人模型：底盘可控、传感器（最少里程计/TF）
- 电池仿真：BatteryState 发布或 Gazebo Sim battery 接口  

### 13.2 ROS2 侧
- Nav2 配置（地图、定位、BT Navigator）
- Skill wrappers（把 ROS2 action 封装成统一接口：call/cancel/status）
- StopBase（紧急停止动作）

### 13.3 Agent（LangGraph）侧
- Kernel 外环图（K1~K6）
- ReAct 内环子图（R1~R8）
- checkpointer + thread_id 管理（持久化与恢复）  
- interrupt/HITL（审批/编辑/继续）  
- streaming 输出到 UI（updates/messages/debug）  

### 13.4 UI/HCI
- 输入：文本/语音（至少文本）
- 输出：状态面板 + LLM token stream + 决策日志
- 审批：interrupt payload 展示 + approve/edit/reject

---

## 14. 你这个 Demo 的“验收标准”（是否真的实现了 ReAct 调度）
只要满足以下 4 条，就说明你的“机器人大脑”不是脚本，而是 ReAct 调度闭环：

1) 任务执行中出现变化（失败/阻塞/用户插队/电量低）时，**LLM 能看到结构化反馈**（R7→R1）。  
2) LLM 会输出可区分的决策类型：**CONTINUE / REPLAN / RETRY / ASK_HUMAN / FINISH**（R2）。  
3) 系统能把决策变成真实动作并执行，且支持 **取消正在跑的动作**（R6）。  
4) 同一 `thread_id` 下可以 **中断→恢复**，且恢复后不会重复执行已发生的副作用（durable execution + task 包裹副作用）。  

---

如果你希望我把 `react.decision`、`react.observation`、`tasks.queue item`、`skills.registry item` 这四个结构 **细化成“字段级（必填/选填/类型/约束/示例）”的接口文档**（便于你直接写 JSON Schema / Pydantic），我也可以在同一套架构下继续补全成“可直接实现”的规格说明。