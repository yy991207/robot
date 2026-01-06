"""
Event_Arbitrate 属性测试

Feature: robot-brain-backend
Property 4: 模式仲裁确定性
Property 5: 抢占规则一致性
Validates: Requirements 2.4, 2.7, 2.8, 7.1-7.5
"""

import pytest
from hypothesis import given, settings, strategies as st
from dataclasses import replace

from robot_brain.core.enums import Mode, UserInterruptType
from robot_brain.core.state import BrainState, RobotState, TasksState, HCIState, WorldState
from robot_brain.service.kernel.event_arbitrate import EventArbitrateNode


class TestModeArbitrationDeterminism:
    """
    Property 4: 模式仲裁确定性
    For any 给定的机器人状态，Event_Arbitrate 节点应产出确定的模式，
    且优先级顺序为：安全事件 > 电量低 > 用户打断 > 正常执行
    Validates: Requirements 2.4, 2.7, 2.8, 7.1
    """

    @settings(max_examples=100)
    @given(battery_pct=st.floats(min_value=0, max_value=9.9))
    def test_critical_battery_triggers_safe_mode(self, battery_pct: float):
        """危急电量应触发 SAFE 模式"""
        state = BrainState(
            robot=RobotState(battery_pct=battery_pct)
        )
        mode, preempt, reason = EventArbitrateNode.arbitrate(state)
        assert mode == Mode.SAFE
        assert preempt is True
        assert "SAFETY" in reason

    @settings(max_examples=100)
    @given(battery_pct=st.floats(min_value=10, max_value=19.9))
    def test_low_battery_triggers_charge_mode(self, battery_pct: float):
        """低电量应触发 CHARGE 模式"""
        state = BrainState(
            robot=RobotState(battery_pct=battery_pct)
        )
        mode, preempt, reason = EventArbitrateNode.arbitrate(state)
        assert mode == Mode.CHARGE
        assert preempt is True
        assert "BATTERY" in reason

    @settings(max_examples=100)
    @given(battery_pct=st.floats(min_value=20, max_value=100))
    def test_normal_battery_no_charge_mode(self, battery_pct: float):
        """正常电量不应触发 CHARGE 模式"""
        state = BrainState(
            robot=RobotState(battery_pct=battery_pct)
        )
        mode, _, _ = EventArbitrateNode.arbitrate(state)
        assert mode != Mode.CHARGE

    def test_collision_risk_triggers_safe_mode(self):
        """碰撞风险应触发 SAFE 模式"""
        state = BrainState(
            world=WorldState(
                obstacles=[{"type": "person", "collision_risk": True}]
            )
        )
        mode, preempt, reason = EventArbitrateNode.arbitrate(state)
        assert mode == Mode.SAFE
        assert preempt is True

    def test_safety_priority_over_battery(self):
        """安全事件优先级高于电量"""
        state = BrainState(
            robot=RobotState(battery_pct=15),  # 低电量
            world=WorldState(
                obstacles=[{"type": "person", "collision_risk": True}]  # 安全事件
            )
        )
        mode, _, reason = EventArbitrateNode.arbitrate(state)
        assert mode == Mode.SAFE
        assert "SAFETY" in reason

    def test_battery_priority_over_user_interrupt(self):
        """电量优先级高于用户中断"""
        state = BrainState(
            robot=RobotState(battery_pct=15),  # 低电量
            hci=HCIState(user_interrupt=UserInterruptType.NEW_GOAL)
        )
        mode, _, reason = EventArbitrateNode.arbitrate(state)
        assert mode == Mode.CHARGE
        assert "BATTERY" in reason

    @settings(max_examples=100)
    @given(battery_pct=st.floats(min_value=20, max_value=100))
    def test_user_stop_triggers_idle_with_preempt(self, battery_pct: float):
        """用户 STOP 指令应触发 IDLE 模式并抢占"""
        state = BrainState(
            robot=RobotState(battery_pct=battery_pct),
            hci=HCIState(user_interrupt=UserInterruptType.STOP)
        )
        mode, preempt, reason = EventArbitrateNode.arbitrate(state)
        assert mode == Mode.IDLE
        assert preempt is True
        assert "USER" in reason

    @settings(max_examples=100)
    @given(battery_pct=st.floats(min_value=20, max_value=100))
    def test_user_pause_triggers_idle_no_preempt(self, battery_pct: float):
        """用户 PAUSE 指令应触发 IDLE 模式但不抢占"""
        state = BrainState(
            robot=RobotState(battery_pct=battery_pct),
            hci=HCIState(user_interrupt=UserInterruptType.PAUSE)
        )
        mode, preempt, reason = EventArbitrateNode.arbitrate(state)
        assert mode == Mode.IDLE
        assert preempt is False

    def test_no_event_with_task_triggers_exec(self):
        """无事件但有任务应触发 EXEC 模式"""
        state = BrainState(
            robot=RobotState(battery_pct=80),
            tasks=TasksState(active_task_id="task_1")
        )
        mode, preempt, _ = EventArbitrateNode.arbitrate(state)
        assert mode == Mode.EXEC
        assert preempt is False

    def test_no_event_no_task_triggers_idle(self):
        """无事件无任务应触发 IDLE 模式"""
        state = BrainState(
            robot=RobotState(battery_pct=80)
        )
        mode, preempt, _ = EventArbitrateNode.arbitrate(state)
        assert mode == Mode.IDLE
        assert preempt is False


class TestPreemptionRulesConsistency:
    """
    Property 5: 抢占规则一致性
    For any 系统状态，当触发 SAFE 模式时必须抢占当前任务；
    当触发 CHARGE 模式时必须抢占主任务；用户 stop 指令必须取消当前任务。
    Validates: Requirements 7.2, 7.3, 7.4, 7.5
    """

    @settings(max_examples=100)
    @given(battery_pct=st.floats(min_value=0, max_value=9.9))
    def test_safe_mode_always_preempts(self, battery_pct: float):
        """SAFE 模式必须抢占"""
        state = BrainState(
            robot=RobotState(battery_pct=battery_pct),
            tasks=TasksState(active_task_id="task_1")
        )
        mode, preempt, _ = EventArbitrateNode.arbitrate(state)
        if mode == Mode.SAFE:
            assert preempt is True

    @settings(max_examples=100)
    @given(battery_pct=st.floats(min_value=10, max_value=19.9))
    def test_charge_mode_always_preempts(self, battery_pct: float):
        """CHARGE 模式必须抢占"""
        state = BrainState(
            robot=RobotState(battery_pct=battery_pct),
            tasks=TasksState(active_task_id="task_1")
        )
        mode, preempt, _ = EventArbitrateNode.arbitrate(state)
        if mode == Mode.CHARGE:
            assert preempt is True

    @settings(max_examples=100)
    @given(battery_pct=st.floats(min_value=20, max_value=100))
    def test_stop_command_always_preempts(self, battery_pct: float):
        """STOP 指令必须抢占"""
        state = BrainState(
            robot=RobotState(battery_pct=battery_pct),
            hci=HCIState(user_interrupt=UserInterruptType.STOP),
            tasks=TasksState(active_task_id="task_1")
        )
        _, preempt, _ = EventArbitrateNode.arbitrate(state)
        assert preempt is True

    @settings(max_examples=100)
    @given(
        battery_pct=st.floats(min_value=20, max_value=100),
        has_collision=st.booleans(),
        interrupt_type=st.sampled_from(list(UserInterruptType))
    )
    def test_mode_is_always_valid_enum(self, battery_pct: float, has_collision: bool, interrupt_type: UserInterruptType):
        """仲裁结果必须是有效的 Mode 枚举"""
        obstacles = [{"collision_risk": True}] if has_collision else []
        state = BrainState(
            robot=RobotState(battery_pct=battery_pct),
            hci=HCIState(user_interrupt=interrupt_type),
            world=WorldState(obstacles=obstacles)
        )
        mode, _, _ = EventArbitrateNode.arbitrate(state)
        assert isinstance(mode, Mode)
        assert mode in list(Mode)
