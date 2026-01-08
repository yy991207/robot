"""
ReAct_Decide 节点

职责：LLM 基于 observation 产出结构化决策
- 理解用户意图（复杂指令拆解）
- 任务规划和决策
输入：messages, skills.registry, tasks.queue, hci.user_utterance
输出：react.decision, tasks.inbox (新任务), trace.log
"""

import json
from dataclasses import replace
from typing import Dict, Any, Optional, Protocol, List

from robot_brain.core.enums import DecisionType, UserInterruptType, TaskStatus
from robot_brain.core.models import Decision
from robot_brain.core.state import BrainState, ReactState
from .base import IReActNode


class ILLMClient(Protocol):
    """LLM 客户端接口"""
    
    async def generate(self, messages: list, system_prompt: str) -> str:
        """生成响应"""
        ...


class MockLLMClient:
    """模拟 LLM 客户端（用于测试）"""
    
    def __init__(self):
        self._response = None
    
    def set_response(self, response: str):
        self._response = response
    
    async def generate(self, messages: list, system_prompt: str) -> str:
        if self._response:
            return self._response
        return json.dumps({
            "type": "CONTINUE",
            "reason": "Task in progress",
            "ops": []
        })


class ReActDecideNode(IReActNode):
    """ReAct 决策节点 - 负责LLM理解和任务拆解"""
    
    SYSTEM_PROMPT = """你是一个家用服务机器人的智能决策器。

## 可用区域
- kitchen (厨房): 坐标 (2, 2)
- living_room (客厅): 坐标 (10, 5)
- bedroom (卧室): 坐标 (2, 7)
- bathroom (浴室/洗手间/卫生间): 坐标 (7, 12)
- charging_station (充电站): 坐标 (-1, 1)

## 可用技能
- NavigateToPose: 导航到指定位置，参数 {"target": "区域英文名"}
- Speak: 语音播报，参数 {"content": "要说的话"}
- StopBase: 停止移动

## 决策类型
- CONTINUE: 继续当前计划
- REPLAN: 重新规划（需要拆解复杂任务）
- FINISH: 任务完成
- ABORT: 中止任务

## 输出格式（JSON）
{
    "type": "CONTINUE|REPLAN|FINISH|ABORT",
    "reason": "决策原因（给用户看的简短回复）",
    "ops": [{"skill": "技能名", "params": {...}}],
    "new_tasks": [{"type": "navigate", "target": "区域英文名"}]
}

## 任务拆解示例

用户: "先去厨房再去卧室"
输出: {
    "type": "REPLAN",
    "reason": "好的，先去厨房，然后去卧室",
    "ops": [{"skill": "NavigateToPose", "params": {"target": "kitchen"}}],
    "new_tasks": [
        {"type": "navigate", "target": "kitchen"},
        {"type": "navigate", "target": "bedroom"}
    ]
}

用户: "回来" 或 "回去充电"
输出: {
    "type": "REPLAN",
    "reason": "好的，正在返回充电站",
    "ops": [{"skill": "NavigateToPose", "params": {"target": "charging_station"}}],
    "new_tasks": [{"type": "navigate", "target": "charging_station"}]
}

## 注意
1. 理解语义，"回来"、"回去"、"回家" 都指返回充电站
2. 复合任务要拆解成多个子任务放入 new_tasks
3. reason 字段是给用户的回复，要简洁友好
4. 只输出 JSON"""

    def __init__(self, llm_client: Optional[ILLMClient] = None):
        self._llm = llm_client or MockLLMClient()
    
    async def execute(self, state: BrainState) -> BrainState:
        """执行 LLM 决策"""
        messages = self._prepare_messages(state)
        response = await self._llm.generate(messages, self.SYSTEM_PROMPT)
        decision, new_tasks = self._parse_decision(response)
        
        # 更新 ReactState
        new_react = ReactState(
            iter=state.react.iter,
            observation=state.react.observation,
            decision=decision,
            proposed_ops=state.react.proposed_ops,
            stop_reason=state.react.stop_reason
        )
        
        # 添加决策到 messages
        new_messages = list(state.messages)
        new_messages.append({
            "role": "assistant",
            "content": response,
            "type": "decision"
        })
        
        # 如果有新任务，直接添加到queue并设置active_task
        new_tasks_state = state.tasks
        if new_tasks:
            import time
            import uuid
            from robot_brain.core.models import Task
            from robot_brain.core.enums import TaskStatus
            
            new_queue = []
            for i, task_data in enumerate(new_tasks):
                target = task_data.get("target", "")
                if target:
                    task = Task(
                        task_id=f"task_{uuid.uuid4().hex[:8]}",
                        goal=f"navigate_to:{target}",
                        priority=80 - i * 5,
                        resources_required=["base"],
                        preemptible=True,
                        status=TaskStatus.PENDING if i > 0 else TaskStatus.RUNNING,
                        created_at=time.time(),
                        metadata={
                            "source": "llm_decompose",
                            "target": target,
                            "sequence": i
                        }
                    )
                    new_queue.append(task)
            
            if new_queue:
                new_tasks_state = replace(
                    state.tasks,
                    queue=new_queue,
                    active_task_id=new_queue[0].task_id,
                    inbox=[]
                )
        
        # 记录日志
        new_log = state.trace.log.copy()
        new_log.append(f"[ReAct_Decide] 决策: {decision.type.value}, 原因: {decision.reason}")
        if new_tasks:
            new_log.append(f"[ReAct_Decide] 拆解任务: {len(new_tasks)} 个")
        new_trace = replace(state.trace, log=new_log)

        # 消费掉本轮用户输入，避免下一轮重复触发进入 EXEC
        new_hci = replace(state.hci, user_utterance="")
        
        return replace(
            state,
            react=new_react,
            messages=new_messages,
            tasks=new_tasks_state,
            trace=new_trace,
            hci=new_hci
        )
    
    def _prepare_messages(self, state: BrainState) -> list:
        """准备 LLM 消息"""
        messages = []
        
        # 添加技能注册表信息
        skill_info = self._format_skill_registry(state)
        messages.append({"role": "system", "content": skill_info})
        
        # 添加当前状态上下文
        context = self._format_context(state)
        messages.append({"role": "system", "content": context})
        
        # 添加历史消息
        for msg in state.messages[-10:]:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
        
        # 添加当前用户输入
        if state.hci.user_utterance:
            messages.append({
                "role": "user",
                "content": f"用户输入: {state.hci.user_utterance}"
            })
        
        return messages
    
    def _format_context(self, state: BrainState) -> str:
        """格式化当前上下文"""
        lines = ["当前状态:"]
        
        # 机器人位置
        if state.robot.pose:
            pose = state.robot.pose
            lines.append(f"- 位置: ({pose.x:.1f}, {pose.y:.1f})")
        
        # 当前任务
        if state.tasks.active_task_id:
            active_task = None
            for task in state.tasks.queue:
                if task.task_id == state.tasks.active_task_id:
                    active_task = task
                    break
            if active_task:
                lines.append(f"- 当前任务: {active_task.goal}")
        
        # 任务队列
        pending = [t for t in state.tasks.queue if t.status == TaskStatus.PENDING]
        if pending:
            lines.append(f"- 待处理任务: {len(pending)} 个")
        
        return "\n".join(lines)
    
    def _format_skill_registry(self, state: BrainState) -> str:
        """格式化技能注册表"""
        if not state.skills.registry:
            return "Available skills: None"
        
        lines = ["Available skills:"]
        for name, skill in state.skills.registry.items():
            lines.append(f"- {name}: {skill.description or 'No description'}")
            if skill.args_schema:
                lines.append(f"  Args: {json.dumps(skill.args_schema)}")
        
        return "\n".join(lines)
    
    def _parse_decision(self, response: str) -> tuple:
        """解析 LLM 响应为决策和新任务"""
        new_tasks = []
        try:
            data = self._extract_json(response)
            
            if "type" not in data:
                raise KeyError("Missing 'type' field")
            
            decision_type = DecisionType(data["type"])
            new_tasks = data.get("new_tasks", [])
            
            decision = Decision(
                type=decision_type,
                reason=data.get("reason", ""),
                plan_patch=data.get("plan_patch"),
                ops=data.get("ops", [])
            )
            return decision, new_tasks
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            decision = Decision(
                type=DecisionType.CONTINUE,
                reason=f"解析失败: {str(e)[:50]}",
                ops=[]
            )
            return decision, new_tasks
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """从文本中提取 JSON"""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 JSON 块
        import re
        # 匹配最外层的 JSON 对象
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        raise json.JSONDecodeError("No JSON found", text, 0)
