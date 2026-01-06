"""
技能注册表属性测试

Feature: robot-brain-backend
Property 10: 技能注册表完整性
Validates: Requirements 4.1
"""

import pytest
from hypothesis import given, settings, strategies as st

from robot_brain.core.enums import InterfaceType
from robot_brain.core.models import SkillDef
from robot_brain.service.skill.registry import SkillRegistry


class TestSkillRegistryCompleteness:
    """
    Property 10: 技能注册表完整性
    For any 注册的技能，必须包含 name、interface_type、args_schema、
    resources_required、preemptible、cancel_supported、timeout_s、error_map 字段。
    Validates: Requirements 4.1
    """

    def test_default_skills_have_all_required_fields(self):
        """默认技能应包含所有必需字段"""
        registry = SkillRegistry()
        
        for skill in registry.list_all():
            assert skill.name, "Skill must have name"
            assert isinstance(skill.interface_type, InterfaceType), "Must have valid interface_type"
            assert isinstance(skill.args_schema, dict), "Must have args_schema dict"
            assert isinstance(skill.resources_required, list), "Must have resources_required list"
            assert isinstance(skill.preemptible, bool), "Must have preemptible bool"
            assert isinstance(skill.cancel_supported, bool), "Must have cancel_supported bool"
            assert isinstance(skill.timeout_s, (int, float)), "Must have timeout_s number"
            assert skill.timeout_s > 0, "timeout_s must be positive"
            assert isinstance(skill.error_map, dict), "Must have error_map dict"

    @settings(max_examples=100)
    @given(
        name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        interface_type=st.sampled_from(list(InterfaceType)),
        timeout_s=st.floats(min_value=1, max_value=3600, allow_nan=False),
        preemptible=st.booleans(),
        cancel_supported=st.booleans()
    )
    def test_registered_skills_preserve_all_fields(
        self, name, interface_type, timeout_s, preemptible, cancel_supported
    ):
        """注册的技能应保留所有字段"""
        registry = SkillRegistry()
        
        skill = SkillDef(
            name=name,
            interface_type=interface_type,
            args_schema={"test": "schema"},
            resources_required=["base"],
            preemptible=preemptible,
            cancel_supported=cancel_supported,
            timeout_s=timeout_s,
            error_map={"ERROR": "RETRY"}
        )
        
        registry.register(skill)
        retrieved = registry.get(name)
        
        assert retrieved is not None
        assert retrieved.name == name
        assert retrieved.interface_type == interface_type
        assert retrieved.args_schema == {"test": "schema"}
        assert retrieved.resources_required == ["base"]
        assert retrieved.preemptible == preemptible
        assert retrieved.cancel_supported == cancel_supported
        assert retrieved.timeout_s == timeout_s
        assert retrieved.error_map == {"ERROR": "RETRY"}

    def test_navigate_skill_exists(self):
        """NavigateToPose 技能应存在"""
        registry = SkillRegistry()
        skill = registry.get("NavigateToPose")
        
        assert skill is not None
        assert skill.interface_type == InterfaceType.ROS2_ACTION
        assert "base" in skill.resources_required
        assert skill.preemptible is True
        assert skill.cancel_supported is True

    def test_stop_skill_exists(self):
        """StopBase 技能应存在"""
        registry = SkillRegistry()
        skill = registry.get("StopBase")
        
        assert skill is not None
        assert skill.interface_type == InterfaceType.ROS2_SERVICE
        assert "base" in skill.resources_required
        assert skill.preemptible is False  # 停止不可被抢占

    def test_speak_skill_exists(self):
        """Speak 技能应存在"""
        registry = SkillRegistry()
        skill = registry.get("Speak")
        
        assert skill is not None
        assert skill.interface_type == InterfaceType.INTERNAL
        assert skill.resources_required == []  # 不占用物理资源

    @settings(max_examples=100)
    @given(name=st.text(min_size=1, max_size=50))
    def test_unregistered_skill_returns_none(self, name: str):
        """未注册的技能应返回 None"""
        registry = SkillRegistry()
        
        # 确保不是默认技能
        if name not in ["NavigateToPose", "StopBase", "Speak"]:
            assert registry.get(name) is None

    def test_skill_validation(self):
        """技能验证应检测缺失字段"""
        registry = SkillRegistry()
        
        # 无效技能：缺少名称
        invalid_skill = SkillDef(
            name="",
            interface_type=InterfaceType.INTERNAL,
            timeout_s=60
        )
        errors = registry.validate_skill(invalid_skill)
        assert len(errors) > 0
        assert any("name" in e.lower() for e in errors)
        
        # 无效技能：超时为负
        invalid_skill2 = SkillDef(
            name="test",
            interface_type=InterfaceType.INTERNAL,
            timeout_s=-1
        )
        errors2 = registry.validate_skill(invalid_skill2)
        assert len(errors2) > 0
        assert any("timeout" in e.lower() for e in errors2)

    def test_get_by_resource(self):
        """按资源查询技能应正确工作"""
        registry = SkillRegistry()
        
        base_skills = registry.get_by_resource("base")
        assert len(base_skills) >= 2  # NavigateToPose 和 StopBase
        
        for skill in base_skills:
            assert "base" in skill.resources_required
