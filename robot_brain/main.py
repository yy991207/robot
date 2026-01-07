"""
Robot Brain 主入口

初始化各组件，配置 streaming 输出
"""

import asyncio
import logging
import signal
import sys
from typing import Optional
from datetime import datetime

from robot_brain.core.state import BrainState
from robot_brain.core.enums import Mode
from robot_brain.graph import BrainGraph, create_brain_graph
from robot_brain.persistence.checkpointer import FileCheckpointer, MemoryCheckpointer
from robot_brain.logging_config import setup_logging, get_logger
from robot_brain.service.react.react_decide import ILLMClient


class RobotBrain:
    """机器人大脑主控制器"""
    
    def __init__(
        self,
        thread_id: str = "robot_brain_main",
        use_file_checkpointer: bool = True,
        checkpoint_dir: str = ".checkpoints",
        llm_client: ILLMClient = None
    ):
        self._thread_id = thread_id
        self._logger = get_logger("robot_brain")
        
        # 初始化检查点存储
        if use_file_checkpointer:
            self._checkpointer = FileCheckpointer(checkpoint_dir)
        else:
            self._checkpointer = MemoryCheckpointer()
        
        # 创建主图
        self._graph = create_brain_graph(
            checkpointer=self._checkpointer,
            on_state_change=self._on_state_change,
            llm_client=llm_client
        )
        
        # 初始化状态
        self._state: Optional[BrainState] = None
        self._running = False
    
    def _on_state_change(self, state: BrainState, node_name: str):
        """状态变化回调"""
        self._logger.info(f"[{node_name}] mode={state.tasks.mode.value}")
        
        # 记录关键状态变化
        if state.react.decision:
            self._logger.debug(
                f"Decision: type={state.react.decision.type.value}, "
                f"reason={state.react.decision.reason}"
            )
        
        if state.skills.running:
            running_skills = [s.skill_name for s in state.skills.running]
            self._logger.debug(f"Running skills: {running_skills}")
    
    def initialize(self, initial_state: Optional[BrainState] = None) -> BrainState:
        """初始化状态"""
        if initial_state:
            self._state = initial_state
        else:
            self._state = BrainState()
        
        self._logger.info("Robot brain initialized")
        return self._state
    
    async def run(
        self,
        max_kernel_iterations: int = 100,
        max_react_iterations: int = 20
    ):
        """运行主循环"""
        if not self._state:
            self._state = self.initialize()
        
        self._running = True
        self._logger.info("Starting robot brain main loop")
        
        try:
            self._state = await self._graph.run_loop(
                state=self._state,
                thread_id=self._thread_id,
                max_kernel_iterations=max_kernel_iterations,
                max_react_iterations=max_react_iterations
            )
        except Exception as e:
            self._logger.error(f"Error in main loop: {e}")
            raise
        finally:
            self._running = False
            self._logger.info("Robot brain main loop stopped")
    
    async def run_once(self) -> BrainState:
        """执行一次循环"""
        if not self._state:
            self._state = self.initialize()
        
        self._state = await self._graph.run_once(
            state=self._state,
            thread_id=self._thread_id
        )
        return self._state
    
    def stop(self):
        """停止运行"""
        self._graph.interrupt()
        self._running = False
        self._logger.info("Stop signal received")
    
    async def resume(self, checkpoint_id: Optional[str] = None) -> Optional[BrainState]:
        """从检查点恢复"""
        self._logger.info(f"Resuming from checkpoint: {checkpoint_id or 'latest'}")
        
        state = await self._graph.resume_from_checkpoint(
            thread_id=self._thread_id,
            checkpoint_id=checkpoint_id
        )
        
        if state:
            self._state = state
            self._logger.info("Successfully resumed from checkpoint")
        else:
            self._logger.warning("No checkpoint found to resume from")
        
        return state
    
    def inject_user_input(self, utterance: str):
        """注入用户输入"""
        if self._state:
            self._state.hci.user_utterance = utterance
            self._logger.info(f"User input injected: {utterance}")
    
    def inject_telemetry(self, pose: dict, twist: dict, battery_pct: float):
        """注入遥测数据"""
        if self._state:
            from robot_brain.core.models import Pose, Twist
            self._state.robot.pose = Pose(**pose)
            self._state.robot.twist = Twist(**twist)
            self._state.robot.battery_pct = battery_pct
    
    @property
    def state(self) -> Optional[BrainState]:
        return self._state
    
    @property
    def is_running(self) -> bool:
        return self._running


async def main():
    """主函数"""
    # 设置日志
    setup_logging(level=logging.INFO)
    logger = get_logger("main")
    
    # 创建机器人大脑
    brain = RobotBrain(
        thread_id=f"robot_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        use_file_checkpointer=True
    )
    
    # 设置信号处理
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        brain.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 初始化并运行
    brain.initialize()
    
    logger.info("Robot brain starting...")
    
    try:
        await brain.run(
            max_kernel_iterations=100,
            max_react_iterations=20
        )
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise
    finally:
        logger.info("Robot brain shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
