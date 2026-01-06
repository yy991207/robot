"""
ReAct_Decide 节点

职责：LLM 基于 observation 产出结构化决策
输入：messages, skills.registry, tasks.queue
输出：react.decision, trace.log
"""

import json
from dataclasses import replace
from typing import Dict, Any, Optional, Protocol

from robot_brain.core.enums import DecisionType
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
        # 默认返回 CONTINUE 决策
        return json.dumps({
            "type": "CONTINUE",
            "reason": "Task in progress",
            "ops": []
        })


class ReActDecideNode(IReActNode):
    """ReAct 决策节点"""
    
    SYSTEM_PROMPT = """你是一个机器人任务调度器。基于当前观测，你需要做出决策。

决策类型：
- CONTINUE: 继续当前计划
- REPLAN: 重新规划（当前方案不可行）
- RETRY: 重试当前操作（临时失败）
- SWITCH_TASK: 切换到其他任务
- ASK_HUMAN: 请求人工干预
- FINISH: 任务完成
- ABORT: 中止任务

请以 JSON 格式返回决策：
{
    "type": "CONTINUE|REPLAN|RETRY|SWITCH_TASK|ASK_HUMAN|FINISH|ABORT",
    "reason": "决策原因",
    "plan_patch": null 或 {"修改内容"},
    "ops": [{"skill": "技能名", "params": {...}}]
}
"""
    
    def __init__(self, llm_client: Optional[ILLMClient] = None):
        self._llm = llm_client or MockLLMClient()
    
    async def execute(self, state: BrainState) -> BrainState:
        """执行 LLM 决策"""
        # 构建 LLM 输入
        messages = self._prepare_messages(state)
        
        # 调用 LLM
        response = await self._llm.generate(messages, self.SYSTEM_PROMPT)
        
        # 解析决策
        decision = self._parse_decision(response)
        
        # 更新状态
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
        
        # 记录日志
        new_log = state.trace.log.copy()
        new_log.append(f"[ReAct_Decide] 决策: {decision.type.value}, 原因: {decision.reason}")
        new_trace = replace(state.trace, log=new_log)
        
        return replace(state, react=new_react, messages=new_messages, trace=new_trace)
    
    def _prepare_messages(self, state: BrainState) -> list:
        """准备 LLM 消息"""
        messages = []
        
        # 添加技能注册表信息
        skill_info = self._format_skill_registry(state)
        messages.append({"role": "system", "content": skill_info})
        
        # 添加历史消息
        for msg in state.messages[-10:]:  # 最近10条
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
        
        return messages
    
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
    
    def _parse_decision(self, response: str) -> Decision:
        """解析 LLM 响应为决策"""
        try:
            # 尝试提取 JSON
            data = self._extract_json(response)
            
            # 检查必要字段
            if "type" not in data:
                raise KeyError("Missing 'type' field")
            
            decision_type = DecisionType(data["type"])
            return Decision(
                type=decision_type,
                reason=data.get("reason", ""),
                plan_patch=data.get("plan_patch"),
                ops=data.get("ops", [])
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            # 解析失败，返回默认决策
            return Decision(
                type=DecisionType.ASK_HUMAN,
                reason=f"Failed to parse LLM response: {response[:100]}",
                ops=[]
            )
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """从文本中提取 JSON"""
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 JSON 块
        import re
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        
        raise json.JSONDecodeError("No JSON found", text, 0)
