"""
Kernel 外环图

组装 K1-K6 节点，实现外环调度
"""

from typing import Dict, Any, Literal
from dataclasses import asdict

from robot_brain.core.state import BrainState
from robot_brain.core.enums import Mode
from robot_brain.service.kernel import (
    HCIIngressNode,
    TelemetrySyncNode,
    WorldUpdateNode,
    EventArbitrateNode,
    TaskQueueNode,
    KernelRouteNode,
    RouteTarget
)


class KernelGraph:
    """Kernel 外环图"""
    
    def __init__(self):
        self._hci_ingress = HCIIngressNode()
        self._telemetry_sync = TelemetrySyncNode()
        self._world_update = WorldUpdateNode()
        self._event_arbitrate = EventArbitrateNode()
        self._task_queue = TaskQueueNode()
        self._kernel_route = KernelRouteNode()
    
    def run(self, state: BrainState) -> BrainState:
        """执行 Kernel 外环"""
        # K1: HCI 输入处理
        state = self._hci_ingress.execute(state)
        
        # K2: 遥测数据同步
        state = self._telemetry_sync.execute(state)
        
        # K3: 世界模型更新
        state = self._world_update.execute(state)
        
        # K4: 事件检测与模式仲裁
        state = self._event_arbitrate.execute(state)
        
        # K5: 任务队列更新
        state = self._task_queue.execute(state)
        
        # K6: 路由决策
        state = self._kernel_route.execute(state)
        
        return state
    
    def get_route_target(self, state: BrainState) -> RouteTarget:
        """获取路由目标"""
        return KernelRouteNode.get_route(state.tasks.mode)
    
    def should_enter_react(self, state: BrainState) -> bool:
        """判断是否应进入 ReAct 内环"""
        return state.tasks.mode == Mode.EXEC


def create_kernel_nodes() -> Dict[str, Any]:
    """创建 Kernel 节点（用于 LangGraph StateGraph）"""
    
    hci_ingress = HCIIngressNode()
    telemetry_sync = TelemetrySyncNode()
    world_update = WorldUpdateNode()
    event_arbitrate = EventArbitrateNode()
    task_queue = TaskQueueNode()
    kernel_route = KernelRouteNode()
    
    def hci_ingress_node(state: Dict[str, Any]) -> Dict[str, Any]:
        brain_state = BrainState._from_dict(state)
        result = hci_ingress.execute(brain_state)
        return result._to_dict()
    
    def telemetry_sync_node(state: Dict[str, Any]) -> Dict[str, Any]:
        brain_state = BrainState._from_dict(state)
        result = telemetry_sync.execute(brain_state)
        return result._to_dict()
    
    def world_update_node(state: Dict[str, Any]) -> Dict[str, Any]:
        brain_state = BrainState._from_dict(state)
        result = world_update.execute(brain_state)
        return result._to_dict()
    
    def event_arbitrate_node(state: Dict[str, Any]) -> Dict[str, Any]:
        brain_state = BrainState._from_dict(state)
        result = event_arbitrate.execute(brain_state)
        return result._to_dict()
    
    def task_queue_node(state: Dict[str, Any]) -> Dict[str, Any]:
        brain_state = BrainState._from_dict(state)
        result = task_queue.execute(brain_state)
        return result._to_dict()
    
    def kernel_route_node(state: Dict[str, Any]) -> Dict[str, Any]:
        brain_state = BrainState._from_dict(state)
        result = kernel_route.execute(brain_state)
        return result._to_dict()
    
    def route_decision(state: Dict[str, Any]) -> Literal["react", "safe", "charge", "idle"]:
        """路由决策函数"""
        mode = state.get("tasks", {}).get("mode", "IDLE")
        if mode == "EXEC":
            return "react"
        elif mode == "SAFE":
            return "safe"
        elif mode == "CHARGE":
            return "charge"
        else:
            return "idle"
    
    return {
        "hci_ingress": hci_ingress_node,
        "telemetry_sync": telemetry_sync_node,
        "world_update": world_update_node,
        "event_arbitrate": event_arbitrate_node,
        "task_queue": task_queue_node,
        "kernel_route": kernel_route_node,
        "route_decision": route_decision
    }
