"""Kernel 节点基类"""

from abc import ABC, abstractmethod
from robot_brain.core.state import BrainState


class IKernelNode(ABC):
    """Kernel 节点接口"""
    
    @abstractmethod
    def execute(self, state: BrainState) -> BrainState:
        """执行节点逻辑"""
        pass
