"""
Human_Approval 节点

职责：关键动作前暂停，等人类 approve/edit/reject
输入：react.proposed_ops.need_approval, approval_payload
输出：触发 interrupt 或处理审批响应
"""

from dataclasses import replace
from typing import Dict, Any, Optional

from robot_brain.core.enums import ApprovalAction
from robot_brain.core.models import ProposedOps
from robot_brain.core.state import BrainState, HCIState, ReactState
from .base import IReActNode


class HumanApprovalNode(IReActNode):
    """人类审批节点"""
    
    async def execute(self, state: BrainState) -> BrainState:
        """处理审批逻辑"""
        proposed_ops = state.react.proposed_ops
        
        if not proposed_ops or not proposed_ops.need_approval:
            # 不需要审批，直接通过
            return state
        
        # 检查是否有审批响应
        approval_response = state.hci.approval_response
        
        if approval_response:
            # 处理审批响应
            return self._handle_approval_response(state, approval_response)
        else:
            # 触发审批中断
            return self._trigger_approval_interrupt(state)
    
    def _trigger_approval_interrupt(self, state: BrainState) -> BrainState:
        """触发审批中断"""
        proposed_ops = state.react.proposed_ops
        
        # 更新 HCI 状态，标记需要审批
        new_hci = HCIState(
            user_utterance=state.hci.user_utterance,
            user_interrupt=state.hci.user_interrupt,
            interrupt_payload={
                "type": "approval_required",
                "payload": proposed_ops.approval_payload
            },
            approval_response=None
        )
        
        # 记录日志
        new_log = state.trace.log.copy()
        new_log.append(f"[Human_Approval] 触发审批中断: {proposed_ops.approval_payload}")
        new_trace = replace(state.trace, log=new_log)
        
        # 设置停止原因为等待审批
        new_react = ReactState(
            iter=state.react.iter,
            observation=state.react.observation,
            decision=state.react.decision,
            proposed_ops=state.react.proposed_ops,
            stop_reason="waiting_for_approval"
        )
        
        return replace(state, hci=new_hci, react=new_react, trace=new_trace)
    
    def _handle_approval_response(self, state: BrainState, response: Dict[str, Any]) -> BrainState:
        """处理审批响应"""
        action = ApprovalAction(response.get("action", "REJECT"))
        
        new_log = state.trace.log.copy()
        new_proposed_ops = state.react.proposed_ops
        new_stop_reason = ""
        
        if action == ApprovalAction.APPROVE:
            # 批准：继续执行原计划
            new_log.append("[Human_Approval] 用户批准，继续执行")
            new_stop_reason = ""
        
        elif action == ApprovalAction.EDIT:
            # 编辑：使用编辑后的参数
            edited_params = response.get("edited_params", {})
            new_proposed_ops = self._apply_edits(new_proposed_ops, edited_params)
            new_log.append(f"[Human_Approval] 用户编辑参数: {edited_params}")
            new_stop_reason = ""
        
        elif action == ApprovalAction.REJECT:
            # 拒绝：取消操作
            new_proposed_ops = ProposedOps(
                to_cancel=new_proposed_ops.to_cancel,
                to_dispatch=[],  # 清空派发
                to_speak=["操作已被用户拒绝"],
                need_approval=False,
                approval_payload={}
            )
            new_log.append("[Human_Approval] 用户拒绝，取消操作")
            new_stop_reason = "user_rejected"
        
        # 清除审批响应
        new_hci = HCIState(
            user_utterance=state.hci.user_utterance,
            user_interrupt=state.hci.user_interrupt,
            interrupt_payload={},
            approval_response=None
        )
        
        new_react = ReactState(
            iter=state.react.iter,
            observation=state.react.observation,
            decision=state.react.decision,
            proposed_ops=new_proposed_ops,
            stop_reason=new_stop_reason
        )
        
        new_trace = replace(state.trace, log=new_log)
        
        return replace(state, hci=new_hci, react=new_react, trace=new_trace)
    
    def _apply_edits(self, ops: ProposedOps, edited_params: Dict[str, Any]) -> ProposedOps:
        """应用编辑后的参数"""
        new_dispatches = []
        for dispatch in ops.to_dispatch:
            new_dispatch = dispatch.copy()
            # 合并编辑后的参数
            if "params" in edited_params:
                new_dispatch["params"] = {
                    **dispatch.get("params", {}),
                    **edited_params["params"]
                }
            new_dispatches.append(new_dispatch)
        
        return ProposedOps(
            to_cancel=ops.to_cancel,
            to_dispatch=new_dispatches,
            to_speak=ops.to_speak,
            need_approval=False,  # 编辑后不再需要审批
            approval_payload={}
        )
    
    @classmethod
    def process_approval(cls, action: ApprovalAction, state: BrainState, edited_params: Optional[Dict] = None) -> BrainState:
        """类方法：处理审批（便于测试）"""
        response = {"action": action.value}
        if edited_params:
            response["edited_params"] = edited_params
        
        new_state = replace(state, hci=replace(state.hci, approval_response=response))
        node = cls()
        import asyncio
        return asyncio.get_event_loop().run_until_complete(node.execute(new_state))
