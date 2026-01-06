"""
ReAct 内环图

组装 R1-R8 节点，实现 ReAct 循环
"""

import asyncio
from typing import Dict, Any, Literal

from robot_brain.core.state import BrainState
from robot_brain.service.react import (
    BuildObservationNode,
    ReActDecideNode,
    CompileOpsNode,
    GuardrailsCheckNode,
    HumanApprovalNode,
    DispatchSkillsNode,
    ObserveResultNode,
    StopOrLoopNode,
    LoopDecision
)


class ReActGraph:
    """ReAct 内环图"""
    
    def __init__(self):
        self._build_observation = BuildObservationNode()
        self._react_decide = ReActDecideNode()
        self._compile_ops = CompileOpsNode()
        self._guardrails_check = GuardrailsCheckNode()
        self._human_approval = HumanApprovalNode()
        self._dispatch_skills = DispatchSkillsNode()
        self._observe_result = ObserveResultNode()
        self._stop_or_loop = StopOrLoopNode()
    
    async def run(self, state: BrainState) -> BrainState:
        """执行 ReAct 内环（单次迭代）"""
        # R1: 构建观测
        state = await self._build_observation.execute(state)
        
        # R2: LLM 决策
        state = await self._react_decide.execute(state)
        
        # R3: 编译操作
        state = await self._compile_ops.execute(state)
        
        # R4: 护栏检查
        state = await self._guardrails_check.execute(state)
        
        # R5: 人类审批
        state = await self._human_approval.execute(state)
        
        # 检查是否需要等待审批
        if state.react.stop_reason == "waiting_for_approval":
            return state
        
        # R6: 派发技能
        state = await self._dispatch_skills.execute(state)
        
        # R7: 观察结果
        state = await self._observe_result.execute(state)
        
        # R8: 停止或循环判断
        state = await self._stop_or_loop.execute(state)
        
        return state
    
    async def run_loop(self, state: BrainState, max_iterations: int = 20) -> BrainState:
        """执行 ReAct 循环直到停止条件"""
        for _ in range(max_iterations):
            state = await self.run(state)
            
            # 检查是否应该停止
            if not StopOrLoopNode.should_continue(state):
                break
        
        return state
    
    def should_continue(self, state: BrainState) -> bool:
        """判断是否应继续循环"""
        return StopOrLoopNode.should_continue(state)


def create_react_nodes() -> Dict[str, Any]:
    """创建 ReAct 节点（用于 LangGraph StateGraph）"""
    
    build_observation = BuildObservationNode()
    react_decide = ReActDecideNode()
    compile_ops = CompileOpsNode()
    guardrails_check = GuardrailsCheckNode()
    human_approval = HumanApprovalNode()
    dispatch_skills = DispatchSkillsNode()
    observe_result = ObserveResultNode()
    stop_or_loop = StopOrLoopNode()
    
    async def build_observation_node(state: Dict[str, Any]) -> Dict[str, Any]:
        brain_state = BrainState._from_dict(state)
        result = await build_observation.execute(brain_state)
        return result._to_dict()
    
    async def react_decide_node(state: Dict[str, Any]) -> Dict[str, Any]:
        brain_state = BrainState._from_dict(state)
        result = await react_decide.execute(brain_state)
        return result._to_dict()
    
    async def compile_ops_node(state: Dict[str, Any]) -> Dict[str, Any]:
        brain_state = BrainState._from_dict(state)
        result = await compile_ops.execute(brain_state)
        return result._to_dict()
    
    async def guardrails_check_node(state: Dict[str, Any]) -> Dict[str, Any]:
        brain_state = BrainState._from_dict(state)
        result = await guardrails_check.execute(brain_state)
        return result._to_dict()
    
    async def human_approval_node(state: Dict[str, Any]) -> Dict[str, Any]:
        brain_state = BrainState._from_dict(state)
        result = await human_approval.execute(brain_state)
        return result._to_dict()
    
    async def dispatch_skills_node(state: Dict[str, Any]) -> Dict[str, Any]:
        brain_state = BrainState._from_dict(state)
        result = await dispatch_skills.execute(brain_state)
        return result._to_dict()
    
    async def observe_result_node(state: Dict[str, Any]) -> Dict[str, Any]:
        brain_state = BrainState._from_dict(state)
        result = await observe_result.execute(brain_state)
        return result._to_dict()
    
    async def stop_or_loop_node(state: Dict[str, Any]) -> Dict[str, Any]:
        brain_state = BrainState._from_dict(state)
        result = await stop_or_loop.execute(brain_state)
        return result._to_dict()
    
    def loop_decision(state: Dict[str, Any]) -> Literal["continue", "exit"]:
        """循环决策函数"""
        brain_state = BrainState._from_dict(state)
        decision, _ = StopOrLoopNode.evaluate(brain_state)
        return "continue" if decision == LoopDecision.CONTINUE else "exit"
    
    def approval_decision(state: Dict[str, Any]) -> Literal["dispatch", "wait"]:
        """审批决策函数"""
        stop_reason = state.get("react", {}).get("stop_reason", "")
        return "wait" if stop_reason == "waiting_for_approval" else "dispatch"
    
    return {
        "build_observation": build_observation_node,
        "react_decide": react_decide_node,
        "compile_ops": compile_ops_node,
        "guardrails_check": guardrails_check_node,
        "human_approval": human_approval_node,
        "dispatch_skills": dispatch_skills_node,
        "observe_result": observe_result_node,
        "stop_or_loop": stop_or_loop_node,
        "loop_decision": loop_decision,
        "approval_decision": approval_decision
    }
