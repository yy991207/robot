"""
Speak 技能

用户通知功能
"""

from typing import Dict, Any, Optional, List, Callable

from robot_brain.core.enums import SkillStatus
from robot_brain.core.models import SkillResult


class SpeakSkill:
    """语音通知技能"""
    
    def __init__(self, output_handler: Optional[Callable[[str], None]] = None):
        self._output_handler = output_handler or print
        self._messages: Dict[str, str] = {}
        self._history: List[Dict[str, Any]] = []
    
    async def execute(self, goal_id: str, params: Dict[str, Any]) -> SkillResult:
        """执行语音通知"""
        message = params.get("message", "")
        
        if not message:
            return SkillResult(
                status=SkillStatus.FAILED,
                error_code="EMPTY_MESSAGE",
                error_msg="Message cannot be empty"
            )
        
        self._messages[goal_id] = message
        self._history.append({
            "goal_id": goal_id,
            "message": message,
            "timestamp": None  # 实际实现中添加时间戳
        })
        
        # 输出消息
        self._output_handler(f"[Robot]: {message}")
        
        # 实际实现中这里可能会：
        # 1. 调用 TTS 服务
        # 2. 发送到 UI
        # 3. 记录日志
        
        return SkillResult(
            status=SkillStatus.SUCCESS,
            metrics={"message_length": len(message)}
        )
    
    async def get_result(self, goal_id: str) -> Optional[SkillResult]:
        """获取结果"""
        if goal_id in self._messages:
            return SkillResult(status=SkillStatus.SUCCESS)
        return None
    
    def get_history(self) -> List[Dict[str, Any]]:
        """获取消息历史"""
        return self._history.copy()
    
    def clear_history(self):
        """清空历史"""
        self._history.clear()
