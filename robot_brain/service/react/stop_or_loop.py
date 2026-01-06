"""
Stop_Or_Loop 节点

职责：判断停止条件或继续下一轮
- 达成目标：FINISH
- 失败可恢复：回 R1（触发二次编排）
- 连续失败/迭代超限：ASK_HUMAN 或 ABORT
输入：react.decision, skills.last_result, robot.distance_to_target, react.iter, tasks.mode
输出：react.stop_reason, 路由决策
"""

from dataclasses import replace
from enum import Enum
from typing import Tuple

from robot_brain.core.enums import DecisionType, SkillStatus, Mode
from robot_brain.core.state import BrainState, ReactState
from .base import IReActNode


class LoopDecision(Enum):
    """循环决策"""
    CONTINUE = "continue"   # 继续下一轮
    EXIT = "exit"           # 退出循环


class StopOrLoopNode(IReActNode):
    """停止或循环判断节点"""
    
    # 配置
    MAX_ITERATIONS = 20           # 最大迭代次数
    MAX_CONSECUTIVE_FAILURES = 3  # 最大连续失败次数
    GOAL_DISTANCE_THRESHOLD = 0.5 # 目标距离阈值（米）
    
    async def execute(self, state: BrainState) -> BrainState:
        """判断是否停止或继续循环"""
        decision, stop_reason = self._evaluate(state)
        
        new_react = ReactState(
            iter=state.react.iter,
            observation=state.react.observation,
            decision=state.react.decision,
            proposed_ops=state.react.proposed_ops,
            stop_reason=stop_reason
        )
        
        # 记录日志
        new_log = state.trace.log.copy()
        new_log.append(f"[Stop_Or_Loop] 决策: {decision.value}, 原因: {stop_reason}")
        
        # 更新 metrics
        new_metrics = state.trace.metrics.copy()
        new_metrics["loop_decision"] = decision.value
        new_trace = replace(state.trace, log=new_log, metrics=new_metrics)
        
        return replace(state, react=new_react, trace=new_trace)
    
    def _evaluate(self, state: BrainState) -> Tuple[LoopDecision, str]:
        """评估是否停止"""
        decision = state.react.decision
        
        # 1. 检查决策类型
        if decision:
            if decision.type == DecisionType.FINISH:
                return LoopDecision.EXIT, "task_completed"
            
            if decision.type == DecisionType.ABORT:
                return LoopDecision.EXIT, "task_aborted"
            
            if decision.type == DecisionType.ASK_HUMAN:
                return LoopDecision.EXIT, "need_human_intervention"
        
        # 2. 检查等待审批
        if state.react.stop_reason == "waiting_for_approval":
            return LoopDecision.EXIT, "waiting_for_approval"
        
        # 3. 检查用户拒绝
        if state.react.stop_reason == "user_rejected":
            return LoopDecision.EXIT, "user_rejected"
        
        # 4. 检查迭代次数
        if state.react.iter >= self.MAX_ITERATIONS:
            return LoopDecision.EXIT, f"max_iterations_reached_{self.MAX_ITERATIONS}"
        
        # 5. 检查连续失败
        failure_count = self._count_consecutive_failures(state)
        if failure_count >= self.MAX_CONSECUTIVE_FAILURES:
            return LoopDecision.EXIT, f"consecutive_failures_{failure_count}"
        
        # 6. 检查模式变化
        if state.tasks.mode in [Mode.SAFE, Mode.CHARGE]:
            return LoopDecision.EXIT, f"mode_changed_to_{state.tasks.mode.value}"
        
        # 7. 检查目标距离（如果接近目标且无运行技能，可能完成）
        if (state.robot.distance_to_target < self.GOAL_DISTANCE_THRESHOLD and
            not state.skills.running and
            state.tasks.active_task_id):
            # 可能完成，但让 LLM 确认
            pass
        
        # 默认继续循环
        return LoopDecision.CONTINUE, ""
    
    def _count_consecutive_failures(self, state: BrainState) -> int:
        """统计连续失败次数"""
        count = 0
        # 从 trace.log 中统计最近的连续失败
        for log_entry in reversed(state.trace.log):
            if "FAILED" in log_entry or "失败" in log_entry:
                count += 1
            elif "SUCCESS" in log_entry or "成功" in log_entry or "完成" in log_entry:
                break
        return count
    
    @classmethod
    def should_continue(cls, state: BrainState) -> bool:
        """类方法：判断是否应继续循环（便于图路由使用）"""
        node = cls()
        decision, _ = node._evaluate(state)
        return decision == LoopDecision.CONTINUE
    
    @classmethod
    def evaluate(cls, state: BrainState) -> Tuple[LoopDecision, str]:
        """类方法：评估停止条件（便于测试）"""
        node = cls()
        return node._evaluate(state)
