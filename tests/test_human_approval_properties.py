"""
Human_Approval 属性测试

Feature: robot-brain-backend
Property 8: 审批响应处理正确性
Validates: Requirements 6.3, 6.4, 6.5, 6.6
"""

import pytest
import asyncio
from hypothesis import given, settings, strategies as st
from dataclasses import replace

from robot_brain.core.enums import ApprovalAction
from robot_brain.core.models import ProposedOps
from robot_brain.core.state import BrainState, HCIState, ReactState
from robot_brain.service.react.human_approval import HumanApprovalNode


class TestApprovalResponseHandling:
    """
    Property 8: 审批响应处理正确性
    For any 审批响应（approve/edit/reject），系统应正确处理：
    approve 继续原计划，edit 使用编辑后参数，reject 取消操作。
    Validates: Requirements 6.3, 6.4, 6.5, 6.6
    """

    def _run_async(self, coro):
        """运行异步函数"""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_approve_continues_original_plan(self):
        """APPROVE 应继续执行原计划"""
        original_dispatches = [{"skill_name": "navigate", "params": {"target": "kitchen"}}]
        state = BrainState(
            hci=HCIState(approval_response={"action": "APPROVE"}),
            react=ReactState(
                proposed_ops=ProposedOps(
                    to_dispatch=original_dispatches,
                    need_approval=True
                )
            )
        )
        
        node = HumanApprovalNode()
        result = self._run_async(node.execute(state))
        
        # 派发列表应保持不变
        assert result.react.proposed_ops.to_dispatch == original_dispatches
        # 审批响应应被清除
        assert result.hci.approval_response is None
        # 停止原因应为空
        assert result.react.stop_reason == ""

    def test_reject_cancels_operation(self):
        """REJECT 应取消操作"""
        state = BrainState(
            hci=HCIState(approval_response={"action": "REJECT"}),
            react=ReactState(
                proposed_ops=ProposedOps(
                    to_dispatch=[{"skill_name": "navigate", "params": {}}],
                    need_approval=True
                )
            )
        )
        
        node = HumanApprovalNode()
        result = self._run_async(node.execute(state))
        
        # 派发列表应被清空
        assert result.react.proposed_ops.to_dispatch == []
        # 应有拒绝通知
        assert any("拒绝" in msg for msg in result.react.proposed_ops.to_speak)
        # 停止原因应为 user_rejected
        assert result.react.stop_reason == "user_rejected"

    @settings(max_examples=100)
    @given(
        original_target=st.text(min_size=1, max_size=50),
        edited_target=st.text(min_size=1, max_size=50)
    )
    def test_edit_uses_edited_params(self, original_target: str, edited_target: str):
        """EDIT 应使用编辑后的参数"""
        state = BrainState(
            hci=HCIState(approval_response={
                "action": "EDIT",
                "edited_params": {"params": {"target": edited_target}}
            }),
            react=ReactState(
                proposed_ops=ProposedOps(
                    to_dispatch=[{"skill_name": "navigate", "params": {"target": original_target}}],
                    need_approval=True
                )
            )
        )
        
        node = HumanApprovalNode()
        result = self._run_async(node.execute(state))
        
        # 参数应被更新
        assert result.react.proposed_ops.to_dispatch[0]["params"]["target"] == edited_target
        # 不再需要审批
        assert result.react.proposed_ops.need_approval is False

    def test_no_approval_needed_passes_through(self):
        """不需要审批时应直接通过"""
        state = BrainState(
            react=ReactState(
                proposed_ops=ProposedOps(
                    to_dispatch=[{"skill_name": "navigate", "params": {}}],
                    need_approval=False
                )
            )
        )
        
        node = HumanApprovalNode()
        result = self._run_async(node.execute(state))
        
        # 状态应保持不变
        assert result.react.proposed_ops.to_dispatch == state.react.proposed_ops.to_dispatch

    def test_triggers_interrupt_when_no_response(self):
        """需要审批但无响应时应触发中断"""
        state = BrainState(
            hci=HCIState(approval_response=None),
            react=ReactState(
                proposed_ops=ProposedOps(
                    to_dispatch=[{"skill_name": "navigate", "params": {}}],
                    need_approval=True,
                    approval_payload={"reason": "test"}
                )
            )
        )
        
        node = HumanApprovalNode()
        result = self._run_async(node.execute(state))
        
        # 应设置中断 payload
        assert result.hci.interrupt_payload.get("type") == "approval_required"
        # 停止原因应为等待审批
        assert result.react.stop_reason == "waiting_for_approval"

    @settings(max_examples=100)
    @given(action=st.sampled_from(list(ApprovalAction)))
    def test_all_approval_actions_handled(self, action: ApprovalAction):
        """所有审批动作都应被处理"""
        response = {"action": action.value}
        if action == ApprovalAction.EDIT:
            response["edited_params"] = {"params": {"test": "value"}}
        
        state = BrainState(
            hci=HCIState(approval_response=response),
            react=ReactState(
                proposed_ops=ProposedOps(
                    to_dispatch=[{"skill_name": "test", "params": {}}],
                    need_approval=True
                )
            )
        )
        
        node = HumanApprovalNode()
        result = self._run_async(node.execute(state))
        
        # 审批响应应被清除
        assert result.hci.approval_response is None
        # 不应抛出异常
        assert result is not None
