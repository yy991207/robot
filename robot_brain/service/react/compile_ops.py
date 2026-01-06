"""
Compile_Ops 节点

职责：把 LLM 决策编译为可执行操作集合
输入：react.decision, skills.running, tasks.preempt_flag, robot.resources
输出：react.proposed_ops
"""

from dataclasses import replace
from typing import List, Dict, Any

from robot_brain.core.enums import DecisionType
from robot_brain.core.models import ProposedOps
from robot_brain.core.state import BrainState, ReactState
from .base import IReActNode


class CompileOpsNode(IReActNode):
    """编译操作节点"""
    
    # 需要审批的技能列表
    APPROVAL_REQUIRED_SKILLS = ["navigate_to_unknown", "manipulate", "dock"]
    
    async def execute(self, state: BrainState) -> BrainState:
        """编译决策为可执行操作"""
        proposed_ops = self._compile(state)
        
        new_react = ReactState(
            iter=state.react.iter,
            observation=state.react.observation,
            decision=state.react.decision,
            proposed_ops=proposed_ops,
            stop_reason=state.react.stop_reason
        )
        
        # 记录日志
        new_log = state.trace.log.copy()
        new_log.append(
            f"[Compile_Ops] 取消: {len(proposed_ops.to_cancel)}, "
            f"派发: {len(proposed_ops.to_dispatch)}, "
            f"需审批: {proposed_ops.need_approval}"
        )
        new_trace = replace(state.trace, log=new_log)
        
        return replace(state, react=new_react, trace=new_trace)
    
    def _compile(self, state: BrainState) -> ProposedOps:
        """编译决策"""
        decision = state.react.decision
        if not decision:
            return ProposedOps()
        
        to_cancel = []
        to_dispatch = []
        to_speak = []
        need_approval = False
        approval_payload = {}
        
        # 根据决策类型处理
        if decision.type == DecisionType.ABORT:
            # 中止：取消所有运行中的技能
            to_cancel = [s.goal_id for s in state.skills.running]
            to_speak = ["任务已中止"]
        
        elif decision.type == DecisionType.FINISH:
            # 完成：取消所有运行中的技能，通知用户
            to_cancel = [s.goal_id for s in state.skills.running]
            to_speak = ["任务已完成"]
        
        elif decision.type == DecisionType.ASK_HUMAN:
            # 求助：暂停并请求人工干预
            to_speak = [f"需要人工干预: {decision.reason}"]
            need_approval = True
            approval_payload = {
                "reason": decision.reason,
                "context": state.react.observation
            }
        
        elif decision.type in [DecisionType.CONTINUE, DecisionType.REPLAN, DecisionType.RETRY]:
            # 继续/重规划/重试：处理操作列表
            if state.tasks.preempt_flag:
                # 需要抢占：先取消当前运行的技能
                to_cancel = [s.goal_id for s in state.skills.running]
            
            # 编译操作
            for op in decision.ops:
                skill_name = op.get("skill", "")
                params = op.get("params", {})
                
                if skill_name:
                    dispatch_item = {
                        "skill_name": skill_name,
                        "params": params
                    }
                    to_dispatch.append(dispatch_item)
                    
                    # 检查是否需要审批
                    if self._requires_approval(skill_name, params):
                        need_approval = True
                        approval_payload = {
                            "skill": skill_name,
                            "params": params,
                            "reason": "High-risk operation requires approval"
                        }
        
        elif decision.type == DecisionType.SWITCH_TASK:
            # 切换任务：取消当前技能
            to_cancel = [s.goal_id for s in state.skills.running]
            to_speak = ["正在切换任务"]
        
        return ProposedOps(
            to_cancel=to_cancel,
            to_dispatch=to_dispatch,
            to_speak=to_speak,
            need_approval=need_approval,
            approval_payload=approval_payload
        )
    
    def _requires_approval(self, skill_name: str, params: Dict[str, Any]) -> bool:
        """判断技能是否需要审批"""
        # 检查技能名称
        if skill_name in self.APPROVAL_REQUIRED_SKILLS:
            return True
        
        # 检查参数中的高风险标记
        if params.get("high_risk", False):
            return True
        
        return False
