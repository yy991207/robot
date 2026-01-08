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
    
    # 区域坐标映射
    ZONE_COORDINATES = {
        "kitchen": (2.0, 2.0),
        "living_room": (10.0, 5.0),
        "bedroom": (2.0, 7.0),
        "bathroom": (7.0, 12.0),
        "charging_station": (-1.0, 1.0),
        # 中文别名
        "厨房": (2.0, 2.0),
        "客厅": (10.0, 5.0),
        "卧室": (2.0, 7.0),
        "浴室": (7.0, 12.0),
        "洗手间": (7.0, 12.0),
        "卫生间": (7.0, 12.0),
        "充电站": (-1.0, 1.0),
    }
    
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
            to_cancel = [s.goal_id for s in state.skills.running]
            to_speak = ["任务已中止"]
        
        elif decision.type == DecisionType.FINISH:
            to_cancel = [s.goal_id for s in state.skills.running]
            to_speak = ["任务已完成"]
        
        elif decision.type == DecisionType.ASK_HUMAN:
            to_speak = [f"需要人工干预: {decision.reason}"]
            need_approval = True
            approval_payload = {
                "reason": decision.reason,
                "context": state.react.observation
            }
        
        elif decision.type in [DecisionType.CONTINUE, DecisionType.REPLAN, DecisionType.RETRY]:
            if state.tasks.preempt_flag:
                to_cancel = [s.goal_id for s in state.skills.running]
            
            for op in decision.ops:
                skill_name = op.get("skill", "")
                params = op.get("params", {})
                
                if skill_name:
                    # 转换参数
                    converted_params = self._convert_params(skill_name, params)
                    dispatch_item = {
                        "skill_name": skill_name,
                        "params": converted_params
                    }
                    to_dispatch.append(dispatch_item)
                    
                    if self._requires_approval(skill_name, params):
                        need_approval = True
                        approval_payload = {
                            "skill": skill_name,
                            "params": converted_params,
                            "reason": "High-risk operation requires approval"
                        }
        
        elif decision.type == DecisionType.SWITCH_TASK:
            to_cancel = [s.goal_id for s in state.skills.running]
            to_speak = ["正在切换任务"]
        
        return ProposedOps(
            to_cancel=to_cancel,
            to_dispatch=to_dispatch,
            to_speak=to_speak,
            need_approval=need_approval,
            approval_payload=approval_payload
        )
    
    def _convert_params(self, skill_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """转换参数 - 区域名转坐标"""
        if skill_name == "Speak":
            # 兼容旧字段：部分 prompt/LLM 可能输出 content
            if "message" not in params and "content" in params:
                new_params = dict(params)
                new_params["message"] = new_params.pop("content")
                return new_params

        if skill_name == "NavigateToPose":
            target = params.get("target", "")
            if target and target in self.ZONE_COORDINATES:
                x, y = self.ZONE_COORDINATES[target]
                return {
                    "target_x": x,
                    "target_y": y,
                    "target_theta": params.get("target_theta", 0.0),
                    "behavior_tree": params.get("behavior_tree", "")
                }
            # 如果已经有坐标，直接返回
            if "target_x" in params:
                return params
        return params
    
    def _requires_approval(self, skill_name: str, params: Dict[str, Any]) -> bool:
        """判断技能是否需要审批"""
        if skill_name in self.APPROVAL_REQUIRED_SKILLS:
            return True
        if params.get("high_risk", False):
            return True
        return False
