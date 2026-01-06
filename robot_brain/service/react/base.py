"""ReAct 节点基类"""

from abc import ABC, abstractmethod
from robot_brain.core.state import BrainState


class IReActNode(ABC):
    """ReAct 节点接口"""
    
    @abstractmethod
    async def execute(self, state: BrainState) -> BrainState:
        """执行节点逻辑（支持异步）"""
        pass
