"""
Kernel_Route 节点

职责：根据 mode 路由到对应处理流程
输入：tasks.mode
输出：路由决策
"""

from dataclasses import replace
from enum import Enum
from typing import Callable, Dict

from robot_brain.core.enums import Mode
from robot_brain.core.state import BrainState
from .base import IKernelNode


class RouteTarget(Enum):
    """路由目标"""
    SAFE_HANDLER = "safe_handler"      # 安全处理流程
    CHARGE_HANDLER = "charge_handler"  # 充电处理流程
    REACT_LOOP = "react_loop"          # ReAct 内环
    IDLE_WAIT = "idle_wait"            # 空闲等待


class KernelRouteNode(IKernelNode):
    """Kernel 路由节点"""
    
    # 模式到路由目标的映射
    MODE_ROUTE_MAP: Dict[Mode, RouteTarget] = {
        Mode.SAFE: RouteTarget.SAFE_HANDLER,
        Mode.CHARGE: RouteTarget.CHARGE_HANDLER,
        Mode.EXEC: RouteTarget.REACT_LOOP,
        Mode.IDLE: RouteTarget.IDLE_WAIT,
    }
    
    def execute(self, state: BrainState) -> BrainState:
        """执行路由决策"""
        mode = state.tasks.mode
        route_target = self._get_route_target(mode)
        
        # 记录路由决策到 trace
        new_log = state.trace.log.copy()
        new_log.append(f"[Kernel_Route] 模式: {mode.value} -> 路由: {route_target.value}")
        new_trace = replace(state.trace, log=new_log)
        
        # 将路由目标存入 metrics 供图路由使用
        new_metrics = state.trace.metrics.copy()
        new_metrics["route_target"] = route_target.value
        new_trace = replace(new_trace, metrics=new_metrics)
        
        return replace(state, trace=new_trace)
    
    def _get_route_target(self, mode: Mode) -> RouteTarget:
        """获取路由目标"""
        return self.MODE_ROUTE_MAP.get(mode, RouteTarget.IDLE_WAIT)
    
    @classmethod
    def get_route(cls, mode: Mode) -> RouteTarget:
        """类方法：获取路由目标（便于测试和外部调用）"""
        return cls.MODE_ROUTE_MAP.get(mode, RouteTarget.IDLE_WAIT)
    
    @classmethod
    def should_enter_react(cls, state: BrainState) -> bool:
        """判断是否应进入 ReAct 内环"""
        return state.tasks.mode == Mode.EXEC
    
    @classmethod
    def should_handle_safety(cls, state: BrainState) -> bool:
        """判断是否应处理安全事件"""
        return state.tasks.mode == Mode.SAFE
    
    @classmethod
    def should_handle_charge(cls, state: BrainState) -> bool:
        """判断是否应处理充电"""
        return state.tasks.mode == Mode.CHARGE
