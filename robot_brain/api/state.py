"""
应用状态管理

管理机器人状态、WebSocket 连接等
"""

import asyncio
import logging
from typing import Dict, List, Set, Any, Optional
from datetime import datetime

from robot_brain.core.state import BrainState
from robot_brain.core.enums import Mode, UserInterruptType
from robot_brain.main import RobotBrain
from robot_brain.llm import QwenLLMClient
from robot_brain.service.skill.registry import SkillRegistry
from robot_brain.simulation import RobotSimulator
from robot_brain.service.chat import ChatService
from robot_brain.service.intent import LLMIntentParser
from robot_brain.persistence import SQLiteCheckpointer
from robot_brain.logging_config import setup_logging, get_logger


class AppState:
    """应用全局状态"""
    
    def __init__(self):
        self._brain: Optional[RobotBrain] = None
        self._simulator: Optional[RobotSimulator] = None
        self._chat_service: Optional[ChatService] = None
        self._llm_client: Optional[QwenLLMClient] = None
        self._checkpointer: Optional[SQLiteCheckpointer] = None
        self._logger = get_logger("api")
        
        # WebSocket 连接管理
        self._ws_connections: Dict[str, Set] = {}  # thread_id -> connections
        
        # 障碍物列表
        self._obstacles: List[Dict[str, Any]] = []
        
        # 模拟循环控制
        self._running = False
        self._simulation_rate = 10  # Hz
    
    async def initialize(self):
        """初始化状态"""
        setup_logging()
        thread_id = f"web_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._logger.info(f"初始化 AppState, thread_id={thread_id}")
        
        # 初始化 LLM
        self._llm_client = QwenLLMClient()
        self._logger.info("LLM 客户端已初始化")
        
        # 初始化持久化
        self._checkpointer = SQLiteCheckpointer("data/robot_brain.db")
        
        # 初始化机器人大脑
        self._brain = RobotBrain(
            thread_id=thread_id,
            use_file_checkpointer=False,
            use_sqlite_checkpointer=True,
            llm_client=self._llm_client
        )
        self._brain.initialize()
        self._logger.info("机器人大脑已初始化")

        # 记录会话起点（驻地）
        self._brain.state.robot.home_pose = self._brain.state.robot.pose
        
        # 初始化技能
        registry = SkillRegistry()
        self._brain.state.skills.registry = registry.to_dict()
        self._logger.info(f"技能注册表已加载: {list(registry.to_dict().keys())}")
        
        # 初始化模拟器
        self._simulator = RobotSimulator()
        
        # 初始化对话服务
        self._chat_service = ChatService(
            self._llm_client,
            checkpointer=self._checkpointer,
            thread_id=thread_id
        )
        
        # 初始化 LLM 意图解析器
        self._intent_parser = LLMIntentParser(self._llm_client)
        self._logger.info("LLM 意图解析器已初始化")
        
        self._running = True
        self._logger.info("AppState 初始化完成")
    
    async def run_simulation_loop(self):
        """运行模拟循环"""
        while self._running:
            try:
                if self._brain and self._brain.state:
                    prev_active_task_id = self._brain.state.tasks.active_task_id

                    # 注入障碍物
                    self._brain.state.world.obstacles = self._obstacles
                    
                    # 尝试从任务提取目标
                    self._sync_simulator_target()
                    
                    # 模拟移动
                    self._brain._state = self._simulator.step(self._brain.state)
                    
                    # 检测任务完成，运行Kernel更新任务队列
                    if self._brain.state.tasks.active_task_id:
                        if self._brain.state.robot.distance_to_target < 0.5:
                            # 到达目标，运行Kernel处理任务切换
                            self._brain._state = self._brain._graph._kernel.run(self._brain.state)
                            self._logger.info(f"任务切换: active_task={self._brain.state.tasks.active_task_id}")

                    # 仅在任务切换点触发一次 ReAct（二次决策/必要时 REPLAN）
                    if prev_active_task_id != self._brain.state.tasks.active_task_id:
                        if self._brain.state.tasks.mode == Mode.EXEC:
                            self._brain._state = await self._brain.run_react_once(node_name="react_task_transition")
                    
                    # 广播位置更新
                    await self._broadcast_position()
                
                await asyncio.sleep(1.0 / self._simulation_rate)
            except Exception as e:
                print(f"Simulation error: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(1.0)
    
    def _sync_simulator_target(self):
        """从任务同步模拟器目标"""
        state = self._brain.state
        
        # 没有活动任务时清空目标
        if not state.tasks.active_task_id:
            if self._simulator._target_x is not None:
                self._logger.info("任务完成，清空导航目标")
                self._simulator._target_x = None
                self._simulator._target_y = None
            self._last_nav_target = None
            return
        
        for task in state.tasks.queue:
            if task.task_id == state.tasks.active_task_id:
                goal = task.goal
                if goal.startswith("navigate_to:"):
                    target = goal.split(":", 1)[1].strip()
                    last_target = getattr(self, '_last_nav_target', None)
                    
                    # 目标变化时重新设置
                    if target != last_target:
                        # 清空旧目标
                        self._simulator._target_x = None
                        self._simulator._target_y = None

                        if target == "home":
                            self._simulator.set_target_pose(
                                x=state.robot.home_pose.x,
                                y=state.robot.home_pose.y,
                                theta=0.0,
                                behavior_tree=""
                            )
                            self._logger.info(
                                f"导航目标: home -> ({self._simulator._target_x}, {self._simulator._target_y})"
                            )
                        else:
                            if self._simulator.set_target(target):
                                self._logger.info(f"导航目标: {target} -> ({self._simulator._target_x}, {self._simulator._target_y})")
                            else:
                                self._logger.warning(f"未知目标: {target}")
                        self._last_nav_target = target
                    break
    
    async def _broadcast_position(self):
        """广播机器人位置"""
        if not self._brain or not self._brain.state:
            return
        
        state = self._brain.state
        # 从四元数计算 yaw 角
        theta = self._quaternion_to_yaw(state.robot.pose)
        
        message = {
            "type": "robot_position",
            "data": {
                "x": state.robot.pose.x,
                "y": state.robot.pose.y,
                "theta": theta,
                "battery_pct": state.robot.battery_pct
            }
        }
        
        await self.broadcast_all(message)
    
    def _quaternion_to_yaw(self, pose) -> float:
        """从四元数计算 yaw 角"""
        import math
        w = pose.orientation_w
        x = pose.orientation_x
        y = pose.orientation_y
        z = pose.orientation_z
        
        # yaw (z-axis rotation)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        return math.atan2(siny_cosp, cosy_cosp)
    
    async def broadcast_all(self, message: dict):
        """广播消息到所有连接"""
        import json
        msg_str = json.dumps(message, ensure_ascii=False)
        
        for connections in self._ws_connections.values():
            for ws in list(connections):
                try:
                    await ws.send_text(msg_str)
                except:
                    connections.discard(ws)
    
    def add_ws_connection(self, thread_id: str, ws):
        """添加 WebSocket 连接"""
        if thread_id not in self._ws_connections:
            self._ws_connections[thread_id] = set()
        self._ws_connections[thread_id].add(ws)
    
    def remove_ws_connection(self, thread_id: str, ws):
        """移除 WebSocket 连接"""
        if thread_id in self._ws_connections:
            self._ws_connections[thread_id].discard(ws)
    
    def parse_intent(self, text: str) -> tuple:
        """解析用户意图（简单规则，用于快速判断）"""
        return UserInterruptType.NONE, {"original": text}
    
    async def parse_intent_llm(self, text: str) -> tuple:
        """使用 LLM 解析用户意图"""
        # 构建上下文
        context = {}
        if self._brain and self._brain.state:
            state = self._brain.state
            context["robot_position"] = {
                "x": state.robot.pose.x,
                "y": state.robot.pose.y
            }
            if state.tasks.active_task_id:
                for task in state.tasks.queue:
                    if task.task_id == state.tasks.active_task_id:
                        context["active_task"] = task.goal
                        break
            # 加载最近对话历史
            if self._checkpointer:
                history = await self._checkpointer.load_chat_history(self._brain.thread_id, 5)
                context["recent_history"] = history
        
        parsed = await self._intent_parser.parse(text, context)
        return self._intent_parser.to_interrupt_payload(parsed)
    
    @property
    def intent_parser(self) -> LLMIntentParser:
        return self._intent_parser
    
    @property
    def brain(self) -> Optional[RobotBrain]:
        return self._brain
    
    @property
    def simulator(self) -> Optional[RobotSimulator]:
        return self._simulator
    
    @property
    def chat_service(self) -> Optional[ChatService]:
        return self._chat_service
    
    @property
    def obstacles(self) -> List[Dict[str, Any]]:
        return self._obstacles
    
    def add_obstacle(self, obstacle: Dict[str, Any]):
        """添加障碍物"""
        self._obstacles.append(obstacle)
    
    def remove_obstacle(self, obstacle_id: str):
        """移除障碍物"""
        self._obstacles = [o for o in self._obstacles if o.get("id") != obstacle_id]
    
    def move_obstacle(self, obstacle_id: str, x: float, y: float):
        """移动障碍物"""
        for o in self._obstacles:
            if o.get("id") == obstacle_id:
                o["x"] = x
                o["y"] = y
                break
