"""
技能注册表

职责：维护技能定义，提供技能查询接口
"""

from typing import Dict, List, Optional

from robot_brain.core.enums import InterfaceType
from robot_brain.core.models import SkillDef


class SkillRegistry:
    """技能注册表"""
    
    def __init__(self):
        self._skills: Dict[str, SkillDef] = {}
        self._init_default_skills()
    
    def _init_default_skills(self):
        """初始化默认技能"""
        # NavigateToPose - 导航技能
        self.register(SkillDef(
            name="NavigateToPose",
            interface_type=InterfaceType.ROS2_ACTION,
            args_schema={
                "required": ["target_x", "target_y"],
                "properties": {
                    "target_x": {"type": "number"},
                    "target_y": {"type": "number"},
                    "target_theta": {"type": "number", "default": 0},
                    "behavior_tree": {"type": "string", "default": ""}
                }
            },
            resources_required=["base"],
            preemptible=True,
            cancel_supported=True,
            timeout_s=300.0,
            error_map={
                "GOAL_REJECTED": "REPLAN",
                "TIMEOUT": "RETRY",
                "BLOCKED": "REPLAN",
                "UNKNOWN": "ASK_HUMAN"
            },
            description="导航到指定位置"
        ))
        
        # StopBase - 停止技能
        self.register(SkillDef(
            name="StopBase",
            interface_type=InterfaceType.ROS2_SERVICE,
            args_schema={},
            resources_required=["base"],
            preemptible=False,
            cancel_supported=False,
            timeout_s=5.0,
            error_map={},
            description="紧急停止底盘"
        ))
        
        # Speak - 语音通知技能
        self.register(SkillDef(
            name="Speak",
            interface_type=InterfaceType.INTERNAL,
            args_schema={
                "required": ["message"],
                "properties": {
                    "message": {"type": "string"}
                }
            },
            resources_required=[],
            preemptible=True,
            cancel_supported=True,
            timeout_s=30.0,
            error_map={},
            description="语音通知用户"
        ))
    
    def register(self, skill: SkillDef) -> None:
        """注册技能"""
        self._skills[skill.name] = skill
    
    def unregister(self, name: str) -> bool:
        """注销技能"""
        if name in self._skills:
            del self._skills[name]
            return True
        return False
    
    def get(self, name: str) -> Optional[SkillDef]:
        """获取技能定义"""
        return self._skills.get(name)
    
    def list_all(self) -> List[SkillDef]:
        """列出所有技能"""
        return list(self._skills.values())
    
    def list_names(self) -> List[str]:
        """列出所有技能名称"""
        return list(self._skills.keys())
    
    def to_dict(self) -> Dict[str, SkillDef]:
        """转换为字典"""
        return self._skills.copy()
    
    def has(self, name: str) -> bool:
        """检查技能是否存在"""
        return name in self._skills
    
    def get_by_resource(self, resource: str) -> List[SkillDef]:
        """获取使用指定资源的技能"""
        return [s for s in self._skills.values() if resource in s.resources_required]
    
    def validate_skill(self, skill: SkillDef) -> List[str]:
        """验证技能定义完整性"""
        errors = []
        
        if not skill.name:
            errors.append("Missing skill name")
        
        if not isinstance(skill.interface_type, InterfaceType):
            errors.append("Invalid interface_type")
        
        if skill.timeout_s <= 0:
            errors.append("timeout_s must be positive")
        
        return errors
