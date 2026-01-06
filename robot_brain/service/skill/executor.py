"""
技能执行器基类

职责：定义技能执行接口，管理技能生命周期
"""

import uuid
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

from robot_brain.core.enums import SkillStatus
from robot_brain.core.models import SkillDef, SkillResult
from .registry import SkillRegistry


class ISkillExecutor(ABC):
    """技能执行器接口"""
    
    @abstractmethod
    async def dispatch(self, skill_name: str, params: Dict[str, Any]) -> str:
        """派发技能，返回 goal_id"""
        pass
    
    @abstractmethod
    async def cancel(self, goal_id: str) -> bool:
        """取消技能"""
        pass
    
    @abstractmethod
    async def get_feedback(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """获取执行反馈"""
        pass
    
    @abstractmethod
    async def get_result(self, goal_id: str) -> Optional[SkillResult]:
        """获取执行结果"""
        pass
    
    @abstractmethod
    async def is_running(self, goal_id: str) -> bool:
        """检查技能是否在运行"""
        pass


class BaseSkillExecutor(ISkillExecutor):
    """技能执行器基类"""
    
    def __init__(self, registry: Optional[SkillRegistry] = None):
        self._registry = registry or SkillRegistry()
        self._running: Dict[str, Dict[str, Any]] = {}
        self._results: Dict[str, SkillResult] = {}
        self._feedbacks: Dict[str, Dict[str, Any]] = {}
    
    async def dispatch(self, skill_name: str, params: Dict[str, Any]) -> str:
        """派发技能"""
        skill_def = self._registry.get(skill_name)
        if not skill_def:
            raise ValueError(f"Skill not found: {skill_name}")
        
        goal_id = f"goal_{uuid.uuid4().hex[:8]}"
        
        self._running[goal_id] = {
            "skill_name": skill_name,
            "params": params,
            "start_time": time.time(),
            "skill_def": skill_def
        }
        
        # 调用具体实现
        await self._do_dispatch(goal_id, skill_def, params)
        
        return goal_id
    
    async def cancel(self, goal_id: str) -> bool:
        """取消技能"""
        if goal_id not in self._running:
            return False
        
        running_info = self._running[goal_id]
        skill_def = running_info["skill_def"]
        
        if not skill_def.cancel_supported:
            return False
        
        # 调用具体实现
        success = await self._do_cancel(goal_id)
        
        if success:
            self._results[goal_id] = SkillResult(
                status=SkillStatus.CANCELLED,
                error_code="CANCELLED",
                error_msg="Skill cancelled by user"
            )
            del self._running[goal_id]
        
        return success
    
    async def get_feedback(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """获取执行反馈"""
        if goal_id not in self._running:
            return None
        
        # 调用具体实现获取最新反馈
        feedback = await self._do_get_feedback(goal_id)
        if feedback:
            self._feedbacks[goal_id] = feedback
        
        return self._feedbacks.get(goal_id)
    
    async def get_result(self, goal_id: str) -> Optional[SkillResult]:
        """获取执行结果"""
        # 先检查是否已有结果
        if goal_id in self._results:
            return self._results[goal_id]
        
        # 检查是否还在运行
        if goal_id in self._running:
            # 调用具体实现检查是否完成
            result = await self._do_get_result(goal_id)
            if result:
                self._results[goal_id] = result
                del self._running[goal_id]
                return result
        
        return None
    
    async def is_running(self, goal_id: str) -> bool:
        """检查技能是否在运行"""
        return goal_id in self._running
    
    # 子类需要实现的方法
    @abstractmethod
    async def _do_dispatch(self, goal_id: str, skill_def: SkillDef, params: Dict[str, Any]) -> None:
        """执行派发（子类实现）"""
        pass
    
    @abstractmethod
    async def _do_cancel(self, goal_id: str) -> bool:
        """执行取消（子类实现）"""
        pass
    
    @abstractmethod
    async def _do_get_feedback(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """获取反馈（子类实现）"""
        pass
    
    @abstractmethod
    async def _do_get_result(self, goal_id: str) -> Optional[SkillResult]:
        """获取结果（子类实现）"""
        pass


class MockSkillExecutor(BaseSkillExecutor):
    """模拟技能执行器（用于测试）"""
    
    def __init__(self, registry: Optional[SkillRegistry] = None):
        super().__init__(registry)
        self._mock_results: Dict[str, SkillResult] = {}
        self._mock_feedbacks: Dict[str, Dict[str, Any]] = {}
    
    def set_mock_result(self, goal_id: str, result: SkillResult):
        """设置模拟结果"""
        self._mock_results[goal_id] = result
    
    def set_mock_feedback(self, goal_id: str, feedback: Dict[str, Any]):
        """设置模拟反馈"""
        self._mock_feedbacks[goal_id] = feedback
    
    async def _do_dispatch(self, goal_id: str, skill_def: SkillDef, params: Dict[str, Any]) -> None:
        """模拟派发"""
        pass
    
    async def _do_cancel(self, goal_id: str) -> bool:
        """模拟取消"""
        return True
    
    async def _do_get_feedback(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """模拟获取反馈"""
        return self._mock_feedbacks.get(goal_id)
    
    async def _do_get_result(self, goal_id: str) -> Optional[SkillResult]:
        """模拟获取结果"""
        return self._mock_results.get(goal_id)
