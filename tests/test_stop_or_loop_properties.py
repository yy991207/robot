"""
Stop_Or_Loop 属性测试

Feature: robot-brain-backend
Property 9: 停止条件判断正确性
Validates: Requirements 3.8
"""

import pytest
from hypothesis import given, settings, strategies as st
from dataclasses import replace

from robot_brain.core.enums import DecisionType, Mode
from robot_brain.core.models import Decision
from robot_brain.core.state import BrainState, ReactState, TasksState, TraceState
from robot_brain.service.react.stop_or_loop import StopOrLoopNode, LoopDecision


class TestStopConditionCorrectness:
    """
    Property 9: 停止条件判断正确性
    For any ReAct 循环状态，当达成目标时应返回 FINISH，
    当迭代超限或连续失败时应返回 ASK_HUMAN 或 ABORT。
    Validates: Requirements 3.8
    """

    def test_finish_decision_exits_loop(self):
        """FINISH 决策应退出循环"""
        state = BrainState(
            react=ReactState(
                decision=Decision(type=DecisionType.FINISH, reason="Task completed")
            )
        )
        
        decision, reason = StopOrLoopNode.evaluate(state)
        
        assert decision == LoopDecision.EXIT
        assert "completed" in reason

    def test_abort_decision_exits_loop(self):
        """ABORT 决策应退出循环"""
        state = BrainState(
            react=ReactState(
                decision=Decision(type=DecisionType.ABORT, reason="Cannot proceed")
            )
        )
        
        decision, reason = StopOrLoopNode.evaluate(state)
        
        assert decision == LoopDecision.EXIT
        assert "aborted" in reason

    def test_ask_human_decision_exits_loop(self):
        """ASK_HUMAN 决策应退出循环"""
        state = BrainState(
            react=ReactState(
                decision=Decision(type=DecisionType.ASK_HUMAN, reason="Need help")
            )
        )
        
        decision, reason = StopOrLoopNode.evaluate(state)
        
        assert decision == LoopDecision.EXIT
        assert "human" in reason

    @settings(max_examples=100)
    @given(iter_count=st.integers(min_value=20, max_value=100))
    def test_max_iterations_exits_loop(self, iter_count: int):
        """超过最大迭代次数应退出循环"""
        state = BrainState(
            react=ReactState(iter=iter_count)
        )
        
        decision, reason = StopOrLoopNode.evaluate(state)
        
        assert decision == LoopDecision.EXIT
        assert "max_iterations" in reason

    @settings(max_examples=100)
    @given(iter_count=st.integers(min_value=0, max_value=19))
    def test_under_max_iterations_continues(self, iter_count: int):
        """未超过最大迭代次数应继续循环"""
        state = BrainState(
            react=ReactState(
                iter=iter_count,
                decision=Decision(type=DecisionType.CONTINUE)
            )
        )
        
        decision, _ = StopOrLoopNode.evaluate(state)
        
        assert decision == LoopDecision.CONTINUE

    def test_consecutive_failures_exits_loop(self):
        """连续失败应退出循环"""
        # 创建包含连续失败日志的状态
        log = [
            "[Skill] FAILED: error1",
            "[Skill] FAILED: error2",
            "[Skill] FAILED: error3",
        ]
        state = BrainState(
            react=ReactState(
                decision=Decision(type=DecisionType.RETRY)
            ),
            trace=TraceState(log=log)
        )
        
        decision, reason = StopOrLoopNode.evaluate(state)
        
        assert decision == LoopDecision.EXIT
        assert "failures" in reason

    def test_safe_mode_exits_loop(self):
        """SAFE 模式应退出循环"""
        state = BrainState(
            tasks=TasksState(mode=Mode.SAFE),
            react=ReactState(
                decision=Decision(type=DecisionType.CONTINUE)
            )
        )
        
        decision, reason = StopOrLoopNode.evaluate(state)
        
        assert decision == LoopDecision.EXIT
        assert "SAFE" in reason

    def test_charge_mode_exits_loop(self):
        """CHARGE 模式应退出循环"""
        state = BrainState(
            tasks=TasksState(mode=Mode.CHARGE),
            react=ReactState(
                decision=Decision(type=DecisionType.CONTINUE)
            )
        )
        
        decision, reason = StopOrLoopNode.evaluate(state)
        
        assert decision == LoopDecision.EXIT
        assert "CHARGE" in reason

    def test_waiting_for_approval_exits_loop(self):
        """等待审批应退出循环"""
        state = BrainState(
            react=ReactState(stop_reason="waiting_for_approval")
        )
        
        decision, reason = StopOrLoopNode.evaluate(state)
        
        assert decision == LoopDecision.EXIT
        assert "approval" in reason

    def test_user_rejected_exits_loop(self):
        """用户拒绝应退出循环"""
        state = BrainState(
            react=ReactState(stop_reason="user_rejected")
        )
        
        decision, reason = StopOrLoopNode.evaluate(state)
        
        assert decision == LoopDecision.EXIT
        assert "rejected" in reason

    @settings(max_examples=100)
    @given(decision_type=st.sampled_from([
        DecisionType.CONTINUE, DecisionType.REPLAN, DecisionType.RETRY
    ]))
    def test_recoverable_decisions_continue_loop(self, decision_type: DecisionType):
        """可恢复的决策应继续循环"""
        state = BrainState(
            react=ReactState(
                iter=5,
                decision=Decision(type=decision_type)
            ),
            tasks=TasksState(mode=Mode.EXEC)
        )
        
        decision, _ = StopOrLoopNode.evaluate(state)
        
        assert decision == LoopDecision.CONTINUE

    def test_should_continue_helper(self):
        """should_continue 辅助方法应正确工作"""
        # 应继续
        state1 = BrainState(
            react=ReactState(
                iter=5,
                decision=Decision(type=DecisionType.CONTINUE)
            ),
            tasks=TasksState(mode=Mode.EXEC)
        )
        assert StopOrLoopNode.should_continue(state1) is True
        
        # 应停止
        state2 = BrainState(
            react=ReactState(
                decision=Decision(type=DecisionType.FINISH)
            )
        )
        assert StopOrLoopNode.should_continue(state2) is False
