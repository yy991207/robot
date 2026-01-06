"""
状态模型属性测试

Feature: robot-brain-backend
Property 1: 状态模型完整性
Property 2: 状态序列化 Round-Trip
Validates: Requirements 1.1-1.8, 5.4, 5.5
"""

import pytest
from hypothesis import given, settings, strategies as st

from robot_brain.core.enums import (
    Mode, DecisionType, UserInterruptType, ApprovalAction,
    SkillStatus, TaskStatus, InterfaceType
)
from robot_brain.core.models import (
    Pose, Twist, Task, SkillDef, RunningSkill, SkillResult,
    Decision, ProposedOps
)
from robot_brain.core.state import (
    HCIState, WorldState, RobotState, TasksState, SkillsState,
    ReactState, TraceState, BrainState
)


# Hypothesis strategies for generating test data
@st.composite
def pose_strategy(draw):
    return Pose(
        x=draw(st.floats(min_value=-1000, max_value=1000, allow_nan=False)),
        y=draw(st.floats(min_value=-1000, max_value=1000, allow_nan=False)),
        z=draw(st.floats(min_value=-100, max_value=100, allow_nan=False)),
        orientation_w=draw(st.floats(min_value=-1, max_value=1, allow_nan=False)),
        orientation_x=draw(st.floats(min_value=-1, max_value=1, allow_nan=False)),
        orientation_y=draw(st.floats(min_value=-1, max_value=1, allow_nan=False)),
        orientation_z=draw(st.floats(min_value=-1, max_value=1, allow_nan=False))
    )


@st.composite
def twist_strategy(draw):
    return Twist(
        linear_x=draw(st.floats(min_value=-10, max_value=10, allow_nan=False)),
        linear_y=draw(st.floats(min_value=-10, max_value=10, allow_nan=False)),
        linear_z=draw(st.floats(min_value=-10, max_value=10, allow_nan=False)),
        angular_x=draw(st.floats(min_value=-5, max_value=5, allow_nan=False)),
        angular_y=draw(st.floats(min_value=-5, max_value=5, allow_nan=False)),
        angular_z=draw(st.floats(min_value=-5, max_value=5, allow_nan=False))
    )


@st.composite
def task_strategy(draw):
    return Task(
        task_id=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N')))),
        goal=draw(st.text(min_size=1, max_size=200)),
        priority=draw(st.integers(min_value=0, max_value=100)),
        deadline=draw(st.one_of(st.none(), st.floats(min_value=0, max_value=1e10, allow_nan=False))),
        resources_required=draw(st.lists(st.sampled_from(["base", "arm", "gripper"]), max_size=3)),
        preemptible=draw(st.booleans()),
        status=draw(st.sampled_from(list(TaskStatus))),
        created_at=draw(st.floats(min_value=0, max_value=1e10, allow_nan=False)),
        metadata=draw(st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50), max_size=5))
    )


@st.composite
def skill_def_strategy(draw):
    return SkillDef(
        name=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N', 'P')))),
        interface_type=draw(st.sampled_from(list(InterfaceType))),
        args_schema=draw(st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50), max_size=5)),
        resources_required=draw(st.lists(st.sampled_from(["base", "arm", "gripper"]), max_size=3)),
        preemptible=draw(st.booleans()),
        cancel_supported=draw(st.booleans()),
        timeout_s=draw(st.floats(min_value=1, max_value=3600, allow_nan=False)),
        error_map=draw(st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50), max_size=5)),
        description=draw(st.text(max_size=200))
    )


@st.composite
def running_skill_strategy(draw):
    return RunningSkill(
        goal_id=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N')))),
        skill_name=draw(st.text(min_size=1, max_size=50)),
        start_time=draw(st.floats(min_value=0, max_value=1e10, allow_nan=False)),
        timeout_s=draw(st.floats(min_value=1, max_value=3600, allow_nan=False)),
        resources_occupied=draw(st.lists(st.sampled_from(["base", "arm", "gripper"]), max_size=3)),
        params=draw(st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50), max_size=5))
    )


@st.composite
def skill_result_strategy(draw):
    return SkillResult(
        status=draw(st.sampled_from(list(SkillStatus))),
        error_code=draw(st.text(max_size=50)),
        error_msg=draw(st.text(max_size=200)),
        metrics=draw(st.dictionaries(st.text(min_size=1, max_size=20), st.floats(allow_nan=False, allow_infinity=False), max_size=5))
    )


@st.composite
def decision_strategy(draw):
    return Decision(
        type=draw(st.sampled_from(list(DecisionType))),
        reason=draw(st.text(max_size=200)),
        plan_patch=draw(st.one_of(st.none(), st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50), max_size=3))),
        ops=draw(st.lists(st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50), max_size=3), max_size=5))
    )


@st.composite
def proposed_ops_strategy(draw):
    return ProposedOps(
        to_cancel=draw(st.lists(st.text(min_size=1, max_size=50), max_size=5)),
        to_dispatch=draw(st.lists(st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50), max_size=3), max_size=5)),
        to_speak=draw(st.lists(st.text(max_size=200), max_size=5)),
        need_approval=draw(st.booleans()),
        approval_payload=draw(st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50), max_size=5))
    )


@st.composite
def hci_state_strategy(draw):
    return HCIState(
        user_utterance=draw(st.text(max_size=500)),
        user_interrupt=draw(st.sampled_from(list(UserInterruptType))),
        interrupt_payload=draw(st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50), max_size=5)),
        approval_response=draw(st.one_of(st.none(), st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50), max_size=3)))
    )


@st.composite
def world_state_strategy(draw):
    return WorldState(
        summary=draw(st.text(max_size=500)),
        zones=draw(st.lists(st.text(min_size=1, max_size=50), max_size=10)),
        obstacles=draw(st.lists(st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50), max_size=3), max_size=10))
    )


@st.composite
def robot_state_strategy(draw):
    return RobotState(
        pose=draw(pose_strategy()),
        twist=draw(twist_strategy()),
        battery_pct=draw(st.floats(min_value=0, max_value=100, allow_nan=False)),
        battery_state=draw(st.sampled_from(["FULL", "CHARGING", "DISCHARGING", "LOW", "CRITICAL"])),
        resources=draw(st.fixed_dictionaries({
            "base_busy": st.booleans(),
            "arm_busy": st.booleans(),
            "gripper_busy": st.booleans()
        })),
        distance_to_target=draw(st.floats(min_value=0, max_value=1000, allow_nan=False))
    )


@st.composite
def tasks_state_strategy(draw):
    return TasksState(
        inbox=draw(st.lists(st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50), max_size=3), max_size=5)),
        queue=draw(st.lists(task_strategy(), max_size=5)),
        active_task_id=draw(st.one_of(st.none(), st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))))),
        mode=draw(st.sampled_from(list(Mode))),
        preempt_flag=draw(st.booleans()),
        preempt_reason=draw(st.text(max_size=100))
    )


@st.composite
def skills_state_strategy(draw):
    registry = {}
    for _ in range(draw(st.integers(min_value=0, max_value=3))):
        skill = draw(skill_def_strategy())
        registry[skill.name] = skill
    return SkillsState(
        registry=registry,
        running=draw(st.lists(running_skill_strategy(), max_size=3)),
        last_result=draw(st.one_of(st.none(), skill_result_strategy()))
    )


@st.composite
def react_state_strategy(draw):
    return ReactState(
        iter=draw(st.integers(min_value=0, max_value=100)),
        observation=draw(st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=100), max_size=10)),
        decision=draw(st.one_of(st.none(), decision_strategy())),
        proposed_ops=draw(st.one_of(st.none(), proposed_ops_strategy())),
        stop_reason=draw(st.text(max_size=100))
    )


@st.composite
def trace_state_strategy(draw):
    return TraceState(
        log=draw(st.lists(st.text(max_size=200), max_size=20)),
        metrics=draw(st.dictionaries(st.text(min_size=1, max_size=20), st.floats(allow_nan=False, allow_infinity=False), max_size=10))
    )


@st.composite
def brain_state_strategy(draw):
    return BrainState(
        messages=draw(st.lists(st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=100), max_size=5), max_size=10)),
        hci=draw(hci_state_strategy()),
        world=draw(world_state_strategy()),
        robot=draw(robot_state_strategy()),
        tasks=draw(tasks_state_strategy()),
        skills=draw(skills_state_strategy()),
        react=draw(react_state_strategy()),
        trace=draw(trace_state_strategy())
    )


class TestStateModelCompleteness:
    """
    Property 1: 状态模型完整性
    For any BrainState 对象，它必须包含所有必需的子状态，且每个子状态的必需字段都存在且类型正确。
    Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7
    """

    @settings(max_examples=100)
    @given(state=brain_state_strategy())
    def test_brain_state_has_all_substates(self, state: BrainState):
        """BrainState 必须包含所有子状态"""
        assert hasattr(state, 'messages')
        assert hasattr(state, 'hci')
        assert hasattr(state, 'world')
        assert hasattr(state, 'robot')
        assert hasattr(state, 'tasks')
        assert hasattr(state, 'skills')
        assert hasattr(state, 'react')
        assert hasattr(state, 'trace')

    @settings(max_examples=100)
    @given(state=hci_state_strategy())
    def test_hci_state_fields(self, state: HCIState):
        """HCIState 必须包含所有必需字段"""
        assert hasattr(state, 'user_utterance')
        assert hasattr(state, 'user_interrupt')
        assert hasattr(state, 'interrupt_payload')
        assert hasattr(state, 'approval_response')
        assert isinstance(state.user_interrupt, UserInterruptType)

    @settings(max_examples=100)
    @given(state=world_state_strategy())
    def test_world_state_fields(self, state: WorldState):
        """WorldState 必须包含所有必需字段"""
        assert hasattr(state, 'summary')
        assert hasattr(state, 'zones')
        assert hasattr(state, 'obstacles')
        assert isinstance(state.zones, list)
        assert isinstance(state.obstacles, list)

    @settings(max_examples=100)
    @given(state=robot_state_strategy())
    def test_robot_state_fields(self, state: RobotState):
        """RobotState 必须包含所有必需字段"""
        assert hasattr(state, 'pose')
        assert hasattr(state, 'twist')
        assert hasattr(state, 'battery_pct')
        assert hasattr(state, 'battery_state')
        assert hasattr(state, 'resources')
        assert hasattr(state, 'distance_to_target')
        assert isinstance(state.pose, Pose)
        assert isinstance(state.twist, Twist)
        assert 0 <= state.battery_pct <= 100

    @settings(max_examples=100)
    @given(state=tasks_state_strategy())
    def test_tasks_state_fields(self, state: TasksState):
        """TasksState 必须包含所有必需字段"""
        assert hasattr(state, 'inbox')
        assert hasattr(state, 'queue')
        assert hasattr(state, 'active_task_id')
        assert hasattr(state, 'mode')
        assert hasattr(state, 'preempt_flag')
        assert hasattr(state, 'preempt_reason')
        assert isinstance(state.mode, Mode)

    @settings(max_examples=100)
    @given(state=skills_state_strategy())
    def test_skills_state_fields(self, state: SkillsState):
        """SkillsState 必须包含所有必需字段"""
        assert hasattr(state, 'registry')
        assert hasattr(state, 'running')
        assert hasattr(state, 'last_result')
        assert isinstance(state.registry, dict)
        assert isinstance(state.running, list)

    @settings(max_examples=100)
    @given(state=react_state_strategy())
    def test_react_state_fields(self, state: ReactState):
        """ReactState 必须包含所有必需字段"""
        assert hasattr(state, 'iter')
        assert hasattr(state, 'observation')
        assert hasattr(state, 'decision')
        assert hasattr(state, 'proposed_ops')
        assert hasattr(state, 'stop_reason')

    @settings(max_examples=100)
    @given(state=trace_state_strategy())
    def test_trace_state_fields(self, state: TraceState):
        """TraceState 必须包含所有必需字段"""
        assert hasattr(state, 'log')
        assert hasattr(state, 'metrics')
        assert isinstance(state.log, list)
        assert isinstance(state.metrics, dict)


class TestStateSerializationRoundTrip:
    """
    Property 2: 状态序列化 Round-Trip
    For any 有效的 BrainState 对象，序列化为 JSON 后再反序列化，应得到与原对象等价的状态。
    Validates: Requirements 1.8, 5.4, 5.5
    """

    @settings(max_examples=100)
    @given(state=brain_state_strategy())
    def test_brain_state_roundtrip(self, state: BrainState):
        """BrainState 序列化后反序列化应等价"""
        serialized = state.serialize()
        deserialized = BrainState.deserialize(serialized)
        
        # 验证关键字段
        assert deserialized.hci.user_utterance == state.hci.user_utterance
        assert deserialized.hci.user_interrupt == state.hci.user_interrupt
        assert deserialized.world.summary == state.world.summary
        assert deserialized.world.zones == state.world.zones
        assert deserialized.robot.battery_pct == state.robot.battery_pct
        assert deserialized.robot.battery_state == state.robot.battery_state
        assert deserialized.tasks.mode == state.tasks.mode
        assert deserialized.tasks.preempt_flag == state.tasks.preempt_flag
        assert deserialized.react.iter == state.react.iter
        assert deserialized.react.stop_reason == state.react.stop_reason
        assert len(deserialized.trace.log) == len(state.trace.log)

    @settings(max_examples=100)
    @given(state=brain_state_strategy())
    def test_serialization_produces_valid_json(self, state: BrainState):
        """序列化应产生有效的 JSON 字符串"""
        import json
        serialized = state.serialize()
        # 应该能被 json.loads 解析
        parsed = json.loads(serialized)
        assert isinstance(parsed, dict)

    @settings(max_examples=100)
    @given(state=brain_state_strategy())
    def test_double_roundtrip(self, state: BrainState):
        """双重 round-trip 应保持一致"""
        serialized1 = state.serialize()
        deserialized1 = BrainState.deserialize(serialized1)
        serialized2 = deserialized1.serialize()
        deserialized2 = BrainState.deserialize(serialized2)
        
        # 两次反序列化的结果应该一致
        assert deserialized1.hci.user_interrupt == deserialized2.hci.user_interrupt
        assert deserialized1.tasks.mode == deserialized2.tasks.mode
        assert deserialized1.react.iter == deserialized2.react.iter
