"""
StopBase 技能

紧急停止底盘
"""

from typing import Dict, Any, Optional

from robot_brain.core.enums import SkillStatus
from robot_brain.core.models import SkillResult


class StopBaseSkill:
    """停止底盘技能"""
    
    def __init__(self):
        self._executed: Dict[str, bool] = {}
    
    async def execute(self, goal_id: str, params: Dict[str, Any]) -> SkillResult:
        """执行停止"""
        self._executed[goal_id] = True
        
        # 实际实现中这里会：
        # 1. 取消所有导航目标
        # 2. 发布零速度命令
        # 3. 等待机器人停止
        
        # await self._cancel_all_navigation()
        # await self._publish_zero_velocity()
        
        return SkillResult(
            status=SkillStatus.SUCCESS,
            metrics={"stop_time": 0.0}
        )
    
    async def get_result(self, goal_id: str) -> Optional[SkillResult]:
        """获取结果"""
        if goal_id in self._executed:
            return SkillResult(status=SkillStatus.SUCCESS)
        return None
    
    def is_executed(self, goal_id: str) -> bool:
        """检查是否已执行"""
        return self._executed.get(goal_id, False)
