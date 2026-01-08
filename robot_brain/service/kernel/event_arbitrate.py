"""
Event_Arbitrate 节点

职责：检测事件并裁决模式（SAFE/CHARGE/EXEC/IDLE），决定是否抢占
输入：robot.*, world.*, hci.user_interrupt, skills.running
输出：tasks.mode, tasks.preempt_flag, trace.log
"""

from dataclasses import replace
from typing import Tuple

from robot_brain.core.enums import Mode, UserInterruptType
from robot_brain.core.state import BrainState, TasksState
from .base import IKernelNode


class EventArbitrateNode(IKernelNode):
    """事件检测与模式仲裁节点"""
    
    # 阈值配置
    BATTERY_LOW_THRESHOLD = 20.0      # 低电量阈值
    BATTERY_CRITICAL_THRESHOLD = 10.0  # 危急电量阈值
    
    # 优先级（数字越大优先级越高）
    PRIORITY_SAFETY = 100
    PRIORITY_BATTERY = 80
    PRIORITY_USER_INTERRUPT = 60
    PRIORITY_TASK = 40
    PRIORITY_IDLE = 0
    
    def execute(self, state: BrainState) -> BrainState:
        """执行模式仲裁"""
        mode, preempt_flag, preempt_reason = self._arbitrate(state)
        
        new_tasks = TasksState(
            inbox=state.tasks.inbox,
            queue=state.tasks.queue,
            active_task_id=state.tasks.active_task_id,
            mode=mode,
            preempt_flag=preempt_flag,
            preempt_reason=preempt_reason
        )
        
        # 记录仲裁日志
        new_log = state.trace.log.copy()
        new_log.append(
            f"[Event_Arbitrate] 模式: {mode.value}, 抢占: {preempt_flag}, 原因: {preempt_reason}"
        )
        new_trace = replace(state.trace, log=new_log)
        
        return replace(state, tasks=new_tasks, trace=new_trace)
    
    def _arbitrate(self, state: BrainState) -> Tuple[Mode, bool, str]:
        """
        模式仲裁逻辑
        优先级：安全事件 > 电量低 > 用户打断 > 主任务 > 空闲
        """
        # 1. 检查安全事件（最高优先级）
        safety_event = self._check_safety_event(state)
        if safety_event:
            return Mode.SAFE, True, f"SAFETY: {safety_event}"
        
        # 2. 检查电量
        battery_event = self._check_battery_event(state)
        if battery_event:
            return Mode.CHARGE, True, f"BATTERY: {battery_event}"
        
        # 3. 检查用户中断
        user_interrupt = self._check_user_interrupt(state)
        if user_interrupt:
            interrupt_type = state.hci.user_interrupt
            if interrupt_type == UserInterruptType.STOP:
                return Mode.IDLE, True, "USER: stop command"
            elif interrupt_type == UserInterruptType.PAUSE:
                return Mode.IDLE, False, "USER: pause command"
            elif interrupt_type == UserInterruptType.NEW_GOAL:
                # 新目标：进入执行模式，可能需要抢占
                has_running = len(state.skills.running) > 0
                return Mode.EXEC, has_running, "USER: new goal"

        # 3.5. 未做外环意图识别时：只要有用户输入，就进入 EXEC 让内环 LLM 接管
        if state.hci.user_utterance and state.hci.user_utterance.strip():
            has_running = len(state.skills.running) > 0
            return Mode.EXEC, has_running, "USER: utterance present (llm_handle)"
        
        # 4. 检查是否有活动任务
        if state.tasks.active_task_id or state.tasks.queue:
            return Mode.EXEC, False, "TASK: active task exists"
        
        # 5. 默认空闲
        return Mode.IDLE, False, "IDLE: no active task"
    
    def _check_safety_event(self, state: BrainState) -> str:
        """检查安全事件"""
        # 检查障碍物碰撞风险
        for obstacle in state.world.obstacles:
            if obstacle.get("collision_risk", False):
                return "collision_risk"
        
        # 检查危急电量
        if state.robot.battery_pct < self.BATTERY_CRITICAL_THRESHOLD:
            return "battery_critical"
        
        # 检查资源异常
        # 可扩展更多安全检查
        
        return ""
    
    def _check_battery_event(self, state: BrainState) -> str:
        """检查电量事件"""
        if state.robot.battery_pct < self.BATTERY_LOW_THRESHOLD:
            return f"low_battery_{state.robot.battery_pct:.1f}%"
        return ""
    
    def _check_user_interrupt(self, state: BrainState) -> bool:
        """检查用户中断"""
        return state.hci.user_interrupt != UserInterruptType.NONE
    
    @classmethod
    def arbitrate(cls, state: BrainState) -> Tuple[Mode, bool, str]:
        """类方法：执行仲裁（便于测试）"""
        node = cls()
        return node._arbitrate(state)
