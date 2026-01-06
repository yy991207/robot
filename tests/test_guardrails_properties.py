"""
Guardrails_Check 属性测试

Feature: robot-brain-backend
Property 6: 资源冲突检测
Validates: Requirements 3.4, 7.6
"""

import pytest
from hypothesis import given, settings, strategies as st

from robot_brain.core.models import RunningSkill
from robot_brain.service.react.guardrails_check import GuardrailsCheckNode


class TestResourceConflictDetection:
    """
    Property 6: 资源冲突检测
    For any 技能派发请求，如果请求的资源与当前运行技能占用的资源冲突，
    Guardrails_And_Resource_Check 节点应拒绝该请求。
    Validates: Requirements 3.4, 7.6
    """

    @settings(max_examples=100)
    @given(resource=st.sampled_from(["base", "arm", "gripper"]))
    def test_busy_resource_detected(self, resource: str):
        """忙碌的资源应被检测到冲突"""
        required = [resource]
        current_resources = {f"{resource}_busy": True}
        running_skills = []
        
        conflict = GuardrailsCheckNode.check_resource_conflict(
            required, current_resources, running_skills
        )
        
        assert conflict is not None
        assert resource in conflict

    @settings(max_examples=100)
    @given(resource=st.sampled_from(["base", "arm", "gripper"]))
    def test_occupied_resource_detected(self, resource: str):
        """被运行中技能占用的资源应被检测到冲突"""
        required = [resource]
        current_resources = {f"{resource}_busy": False}
        running_skills = [
            RunningSkill(
                goal_id="test_goal",
                skill_name="test_skill",
                start_time=0,
                timeout_s=60,
                resources_occupied=[resource]
            )
        ]
        
        conflict = GuardrailsCheckNode.check_resource_conflict(
            required, current_resources, running_skills
        )
        
        assert conflict is not None
        assert resource in conflict

    @settings(max_examples=100)
    @given(resource=st.sampled_from(["base", "arm", "gripper"]))
    def test_free_resource_no_conflict(self, resource: str):
        """空闲的资源不应有冲突"""
        required = [resource]
        current_resources = {f"{resource}_busy": False}
        running_skills = []
        
        conflict = GuardrailsCheckNode.check_resource_conflict(
            required, current_resources, running_skills
        )
        
        assert conflict is None

    @settings(max_examples=100)
    @given(
        required=st.lists(st.sampled_from(["base", "arm", "gripper"]), min_size=1, max_size=3, unique=True),
        occupied=st.lists(st.sampled_from(["base", "arm", "gripper"]), max_size=3, unique=True)
    )
    def test_any_overlap_causes_conflict(self, required: list, occupied: list):
        """任何资源重叠都应导致冲突"""
        current_resources = {f"{r}_busy": False for r in ["base", "arm", "gripper"]}
        running_skills = [
            RunningSkill(
                goal_id="test_goal",
                skill_name="test_skill",
                start_time=0,
                timeout_s=60,
                resources_occupied=occupied
            )
        ] if occupied else []
        
        conflict = GuardrailsCheckNode.check_resource_conflict(
            required, current_resources, running_skills
        )
        
        # 检查是否有重叠
        overlap = set(required) & set(occupied)
        if overlap:
            assert conflict is not None
        else:
            assert conflict is None

    def test_empty_required_no_conflict(self):
        """不需要资源的技能不应有冲突"""
        required = []
        current_resources = {"base_busy": True, "arm_busy": True}
        running_skills = [
            RunningSkill(
                goal_id="test_goal",
                skill_name="test_skill",
                start_time=0,
                timeout_s=60,
                resources_occupied=["base", "arm"]
            )
        ]
        
        conflict = GuardrailsCheckNode.check_resource_conflict(
            required, current_resources, running_skills
        )
        
        assert conflict is None

    @settings(max_examples=100)
    @given(
        r1=st.sampled_from(["base", "arm", "gripper"]),
        r2=st.sampled_from(["base", "arm", "gripper"])
    )
    def test_multiple_resources_all_checked(self, r1: str, r2: str):
        """多个资源都应被检查"""
        required = list(set([r1, r2]))  # 去重
        current_resources = {f"{r1}_busy": True}  # r1 忙碌
        running_skills = []
        
        conflict = GuardrailsCheckNode.check_resource_conflict(
            required, current_resources, running_skills
        )
        
        # r1 忙碌，应该有冲突
        assert conflict is not None
        assert r1 in conflict
