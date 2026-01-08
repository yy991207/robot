"""
LangGraph 图定义

主图组装，连接 Kernel 外环和 ReAct 内环
"""

import asyncio
from typing import Dict, Any, Optional, Literal, Callable
from enum import Enum

from robot_brain.core.state import BrainState
from robot_brain.core.enums import Mode
from robot_brain.persistence.checkpointer import MemoryCheckpointer, FileCheckpointer, Checkpoint
from robot_brain.persistence.sqlite_checkpointer import SQLiteCheckpointer
from robot_brain.graph.kernel_graph import KernelGraph, create_kernel_nodes
from robot_brain.graph.react_graph import ReActGraph, create_react_nodes
from robot_brain.service.react.react_decide import ILLMClient


class GraphPhase(Enum):
    """图执行阶段"""
    KERNEL = "kernel"
    REACT = "react"
    IDLE = "idle"
    SAFE = "safe"
    CHARGE = "charge"


class BrainGraph:
    """
    机器人大脑主图
    
    连接 Kernel 外环和 ReAct 内环，支持：
    - 状态持久化（SQLite）
    - 中断处理
    - 流式输出
    """
    
    def __init__(
        self,
        checkpointer: Optional[MemoryCheckpointer | FileCheckpointer] = None,
        sqlite_checkpointer: Optional[SQLiteCheckpointer] = None,
        on_state_change: Optional[Callable[[BrainState, str], None]] = None,
        llm_client: ILLMClient = None
    ):
        self._kernel = KernelGraph()
        self._react = ReActGraph(llm_client=llm_client)
        self._checkpointer = checkpointer or MemoryCheckpointer()
        self._sqlite_checkpointer = sqlite_checkpointer
        self._on_state_change = on_state_change
        self._interrupted = False
    
    def _notify_state_change(self, state: BrainState, node_name: str):
        """通知状态变化"""
        if self._on_state_change:
            self._on_state_change(state, node_name)
    
    def _save_checkpoint(
        self,
        thread_id: str,
        state: BrainState,
        node_name: str
    ) -> str:
        """保存检查点"""
        # 内存/文件检查点
        cp_id = self._checkpointer.save(
            thread_id=thread_id,
            state=state,
            node_name=node_name
        )
        
        # SQLite 检查点（异步，但这里同步调用）
        if self._sqlite_checkpointer:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(
                        self._sqlite_checkpointer.save_checkpoint(
                            thread_id, state, node_name
                        )
                    )
                else:
                    loop.run_until_complete(
                        self._sqlite_checkpointer.save_checkpoint(
                            thread_id, state, node_name
                        )
                    )
            except RuntimeError:
                # 没有事件循环，创建新的
                asyncio.run(
                    self._sqlite_checkpointer.save_checkpoint(
                        thread_id, state, node_name
                    )
                )
        
        return cp_id
    
    def _load_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: Optional[str] = None
    ) -> Optional[Checkpoint]:
        """加载检查点"""
        return self._checkpointer.load(thread_id, checkpoint_id)
    
    def interrupt(self):
        """中断执行"""
        self._interrupted = True
    
    def resume(self):
        """恢复执行"""
        self._interrupted = False
    
    async def run_once(
        self,
        state: BrainState,
        thread_id: str = "default"
    ) -> BrainState:
        """执行一次完整循环（Kernel + 可能的 ReAct）"""
        # 执行 Kernel 外环
        state = self._kernel.run(state)
        self._save_checkpoint(thread_id, state, "kernel")
        self._notify_state_change(state, "kernel")
        
        # 根据模式决定下一步
        if state.tasks.mode == Mode.EXEC:
            # 进入 ReAct 内环
            state = await self._react.run(state)
            self._save_checkpoint(thread_id, state, "react")
            self._notify_state_change(state, "react")
        
        return state
    
    async def run_loop(
        self,
        state: BrainState,
        thread_id: str = "default",
        max_kernel_iterations: int = 100,
        max_react_iterations: int = 20
    ) -> BrainState:
        """
        执行主循环
        
        外层 Kernel 循环持续运行，内层 ReAct 循环在 EXEC 模式下执行
        """
        self._interrupted = False
        
        for _ in range(max_kernel_iterations):
            if self._interrupted:
                break
            
            # 执行 Kernel 外环
            state = self._kernel.run(state)
            self._save_checkpoint(thread_id, state, "kernel")
            self._notify_state_change(state, "kernel")
            
            # 根据模式决定下一步
            if state.tasks.mode == Mode.EXEC:
                # 执行 ReAct 内环循环
                state = await self._react.run_loop(state, max_react_iterations)
                self._save_checkpoint(thread_id, state, "react_complete")
                self._notify_state_change(state, "react_complete")
            
            elif state.tasks.mode == Mode.SAFE:
                # 安全模式：等待恢复
                self._notify_state_change(state, "safe_mode")
            
            elif state.tasks.mode == Mode.CHARGE:
                # 充电模式：等待充电完成
                self._notify_state_change(state, "charge_mode")
            
            else:
                # IDLE 模式：等待新任务
                self._notify_state_change(state, "idle")
        
        return state
    
    async def resume_from_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: Optional[str] = None
    ) -> Optional[BrainState]:
        """从检查点恢复执行"""
        checkpoint = self._load_checkpoint(thread_id, checkpoint_id)
        if not checkpoint:
            return None
        
        state = checkpoint.state
        
        # 根据检查点位置决定恢复策略
        if checkpoint.node_name == "kernel":
            # 从 Kernel 后恢复，检查是否需要进入 ReAct
            if state.tasks.mode == Mode.EXEC:
                state = await self._react.run(state)
                self._save_checkpoint(thread_id, state, "react")
        
        elif checkpoint.node_name == "react":
            # 从 ReAct 中恢复，继续 ReAct 循环
            if self._react.should_continue(state):
                state = await self._react.run(state)
                self._save_checkpoint(thread_id, state, "react")
        
        return state
    
    def get_phase(self, state: BrainState) -> GraphPhase:
        """获取当前执行阶段"""
        mode = state.tasks.mode
        if mode == Mode.EXEC:
            return GraphPhase.REACT
        elif mode == Mode.SAFE:
            return GraphPhase.SAFE
        elif mode == Mode.CHARGE:
            return GraphPhase.CHARGE
        else:
            return GraphPhase.IDLE


def create_brain_graph(
    checkpointer: Optional[MemoryCheckpointer | FileCheckpointer] = None,
    sqlite_checkpointer: Optional[SQLiteCheckpointer] = None,
    on_state_change: Optional[Callable[[BrainState, str], None]] = None,
    llm_client: ILLMClient = None
) -> BrainGraph:
    """创建机器人大脑图实例"""
    return BrainGraph(checkpointer, sqlite_checkpointer, on_state_change, llm_client)


__all__ = [
    "BrainGraph",
    "GraphPhase",
    "create_brain_graph",
    "KernelGraph",
    "ReActGraph",
    "create_kernel_nodes",
    "create_react_nodes"
]
