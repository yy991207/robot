"""
Robot Brain CLI 交互入口

支持终端交互，接收用户指令
"""

import asyncio
import sys
from datetime import datetime

from robot_brain.core.state import BrainState
from robot_brain.core.enums import Mode
from robot_brain.main import RobotBrain
from robot_brain.logging_config import setup_logging, get_logger
from robot_brain.llm import QwenLLMClient
from robot_brain.service.skill.registry import SkillRegistry
from robot_brain.simulation import RobotSimulator
from robot_brain.service.chat import ChatService
from robot_brain.persistence import SQLiteCheckpointer


class RobotBrainCLI:
    """终端交互控制器"""
    
    def __init__(self, use_sqlite: bool = True):
        self._brain: RobotBrain = None
        self._logger = get_logger("cli")
        self._running = False
        self._simulator = RobotSimulator()
        self._chat_service: ChatService = None
        self._use_sqlite = use_sqlite
    
    async def start(self):
        """启动交互模式"""
        setup_logging()
        
        print("=" * 50)
        print("Robot Brain CLI")
        print("=" * 50)
        print("命令 (以/开头):")
        print("  /status  - 查看当前状态")
        print("  /map     - 查看地图")
        print("  /prompt  - 查看LLM输入")
        print("  /run     - 执行一次循环")
        print("  /help    - 显示帮助")
        print("  /quit    - 退出程序")
        print("交互指令 (直接输入):")
        print("  stop/停止      - 紧急停止")
        print("  pause/暂停     - 暂停当前任务")
        print("  go to <地点>   - 导航到指定位置")
        print("  其他文本       - 与机器人对话")
        print("=" * 50)
        
        # 初始化机器人大脑（使用真实 Qwen LLM）
        llm_client = QwenLLMClient()
        thread_id = f"cli_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self._brain = RobotBrain(
            thread_id=thread_id,
            use_file_checkpointer=False,
            use_sqlite_checkpointer=self._use_sqlite,
            llm_client=llm_client
        )
        self._brain.initialize()
        
        # 注册默认技能到状态
        self._init_skills()
        
        # 初始化对话服务（带持久化）
        self._chat_service = ChatService(
            llm_client,
            checkpointer=self._brain.sqlite_checkpointer,
            thread_id=thread_id
        )
        
        self._running = True
        await self._interaction_loop()
    
    def _init_skills(self):
        """初始化技能注册表到状态"""
        registry = SkillRegistry()
        self._brain.state.skills.registry = registry.to_dict()
    
    async def _interaction_loop(self):
        """交互主循环"""
        while self._running:
            try:
                # 异步读取用户输入
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("\n> ")
                )
                
                await self._handle_input(user_input.strip())
                
            except EOFError:
                break
            except KeyboardInterrupt:
                print("\n收到中断信号，退出...")
                break
    
    async def _handle_input(self, text: str):
        """处理用户输入"""
        if not text:
            return
        
        # 斜杠命令
        if text.startswith("/"):
            cmd = text[1:].lower()
            
            if cmd in ["quit", "exit", "q"]:
                self._running = False
                print("再见!")
                return
            
            if cmd == "status":
                self._show_status()
                return
            
            if cmd == "run":
                await self._run_once()
                return
            
            if cmd == "help":
                self._show_help()
                return
            
            if cmd == "map":
                self._show_map()
                return
            
            if cmd == "prompt":
                self._show_prompt()
                return
            
            print(f"[未知命令] /{cmd}，输入 /help 查看帮助")
            return
        
        # 注入用户输入
        self._brain.inject_user_input(text)
        
        # 检查是否是指令类输入
        from robot_brain.core.enums import UserInterruptType
        from robot_brain.service.kernel.hci_ingress import HCIIngressNode
        
        interrupt_type, _ = HCIIngressNode.parse_intent(text)
        
        if interrupt_type == UserInterruptType.NONE:
            # 普通对话
            await self._chat(text)
        else:
            # 指令类输入，执行任务循环
            print(f"[指令已接收] {text}")
            await self._run_once()
    
    async def _run_once(self):
        """执行一次循环"""
        print("[执行中...]")
        try:
            # 先模拟机器人移动
            self._brain._state = self._simulator.step(self._brain.state)
            
            # 执行大脑循环
            state = await self._brain.run_once()
            self._print_result(state)
        except Exception as e:
            print(f"[错误] {e}")
    
    async def _chat(self, text: str):
        """流式闲聊对话"""
        print("[机器人] ", end="", flush=True)
        try:
            async for chunk in self._chat_service.chat_stream(text):
                print(chunk, end="", flush=True)
            print()  # 换行
        except Exception as e:
            print(f"\n[对话错误] {e}")
    
    def _show_status(self):
        """显示当前状态"""
        state = self._brain.state
        if not state:
            print("[状态] 未初始化")
            return
        
        print(f"[状态]")
        print(f"  模式: {state.tasks.mode.value}")
        print(f"  当前任务: {state.tasks.active_task_id or '无'}")
        print(f"  任务队列: {len(state.tasks.queue)} 个")
        print(f"  运行中技能: {[s.skill_name for s in state.skills.running]}")
        print(f"  电量: {state.robot.battery_pct:.1f}%")
        print(f"  位置: ({state.robot.pose.x:.1f}, {state.robot.pose.y:.1f})")
        
        if state.react.decision:
            print(f"  最近决策: {state.react.decision.type.value}")
    
    def _print_result(self, state: BrainState):
        """打印执行结果"""
        # 打印最新日志
        if state.trace.log:
            print("\n[日志]")
            for log in state.trace.log[-5:]:
                print(f"  {log}")
        
        # 打印决策
        if state.react.decision:
            print(f"\n[决策] {state.react.decision.type.value}: {state.react.decision.reason}")
        
        # 打印要说的话
        if state.react.proposed_ops and state.react.proposed_ops.to_speak:
            print("\n[机器人说]")
            for msg in state.react.proposed_ops.to_speak:
                print(f"  {msg}")
    
    def _show_map(self):
        """显示地图"""
        state = self._brain.state
        robot_x = state.robot.pose.x if state else 0
        robot_y = state.robot.pose.y if state else 0
        
        # 区域定义
        zones = {
            "charging_station": {"x": -1, "y": 1, "symbol": "C"},
            "kitchen": {"x": 2, "y": 2, "symbol": "K"},
            "living_room": {"x": 10, "y": 5, "symbol": "L"},
            "bedroom": {"x": 2, "y": 7, "symbol": "B"},
            "bathroom": {"x": 7, "y": 12, "symbol": "W"},
        }
        
        print("\n[地图] (R=机器人, C=充电站, K=厨房, L=客厅, B=卧室, W=浴室)")
        print("    " + "".join([f"{i:2}" for i in range(-2, 16)]))
        print("   +" + "-" * 36 + "+")
        
        for y in range(15, -1, -1):
            row = f"{y:2} |"
            for x in range(-2, 16):
                # 检查是否是机器人位置
                if abs(x - robot_x) < 0.5 and abs(y - robot_y) < 0.5:
                    row += " R"
                # 检查是否是区域中心
                elif any(abs(x - z["x"]) < 1 and abs(y - z["y"]) < 1 for z in zones.values()):
                    for name, z in zones.items():
                        if abs(x - z["x"]) < 1 and abs(y - z["y"]) < 1:
                            row += f" {z['symbol']}"
                            break
                else:
                    row += " ."
            row += " |"
            print(row)
        
        print("   +" + "-" * 36 + "+")
        print(f"\n机器人位置: ({robot_x:.1f}, {robot_y:.1f})")
        print("区域坐标:")
        for name, z in zones.items():
            print(f"  {name}: ({z['x']}, {z['y']})")
    
    def _show_help(self):
        """显示帮助"""
        print("\n命令 (以/开头):")
        print("  /status  - 查看当前状态")
        print("  /map     - 查看地图")
        print("  /prompt  - 查看LLM输入")
        print("  /run     - 执行一次循环")
        print("  /help    - 显示帮助")
        print("  /quit    - 退出程序")
        print("\n交互指令 (直接输入):")
        print("  stop/停止      - 紧急停止")
        print("  pause/暂停     - 暂停任务")
        print("  go to <地点>   - 导航")
    
    def _show_prompt(self):
        """显示LLM看到的信息"""
        state = self._brain.state
        if not state:
            print("[观测] 状态未初始化")
            return
        
        print("\n" + "=" * 50)
        print("[LLM 输入信息]")
        print("=" * 50)
        
        # 系统提示词
        from robot_brain.service.react.react_decide import ReActDecideNode
        print("\n[系统提示词]")
        print(ReActDecideNode.SYSTEM_PROMPT)
        
        # 技能注册表
        print("\n[可用技能]")
        for name, skill in state.skills.registry.items():
            print(f"  - {name}: {skill.description}")
        
        # 观测信息
        print("\n[当前观测]")
        obs = state.react.observation
        if obs:
            import json
            print(json.dumps(obs, indent=2, ensure_ascii=False))
        else:
            print("  (无观测数据，需要先执行 run)")
        
        # 最近消息
        print("\n[最近消息]")
        for msg in state.messages[-5:]:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:100]
            print(f"  [{role}] {content}...")
        
        print("=" * 50)


async def main():
    cli = RobotBrainCLI()
    await cli.start()


if __name__ == "__main__":
    asyncio.run(main())
