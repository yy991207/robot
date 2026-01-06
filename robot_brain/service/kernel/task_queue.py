"""
Task_Queue 节点

职责：把用户话/新目标转成结构化任务，更新队列与优先级
输入：hci.user_utterance, tasks.inbox, skills.registry
输出：tasks.queue, tasks.active_task_id
"""

import time
import uuid
from dataclasses import replace
from typing import List, Dict, Any, Optional

from robot_brain.core.enums import UserInterruptType, TaskStatus
from robot_brain.core.models import Task
from robot_brain.core.state import BrainState, TasksState
from .base import IKernelNode


class TaskQueueNode(IKernelNode):
    """任务队列管理节点"""
    
    # 默认优先级
    DEFAULT_PRIORITY = 50
    HIGH_PRIORITY = 80
    LOW_PRIORITY = 20
    
    def execute(self, state: BrainState) -> BrainState:
        """更新任务队列"""
        new_queue = list(state.tasks.queue)
        new_inbox = list(state.tasks.inbox)
        active_task_id = state.tasks.active_task_id
        
        # 处理用户中断带来的新目标
        if state.hci.user_interrupt == UserInterruptType.NEW_GOAL:
            new_task = self._create_task_from_interrupt(state)
            if new_task:
                new_queue.append(new_task)
                new_inbox.clear()  # 清空 inbox
        
        # 处理 inbox 中的待处理目标
        for goal_data in new_inbox:
            task = self._create_task_from_goal(goal_data)
            if task:
                new_queue.append(task)
        new_inbox = []
        
        # 按优先级排序（高优先级在前）
        new_queue.sort(key=lambda t: -t.priority)
        
        # 选择活动任务
        if not active_task_id and new_queue:
            # 选择优先级最高的待处理任务
            for task in new_queue:
                if task.status == TaskStatus.PENDING:
                    active_task_id = task.task_id
                    task.status = TaskStatus.RUNNING
                    break
        
        new_tasks = TasksState(
            inbox=new_inbox,
            queue=new_queue,
            active_task_id=active_task_id,
            mode=state.tasks.mode,
            preempt_flag=state.tasks.preempt_flag,
            preempt_reason=state.tasks.preempt_reason
        )
        
        # 记录日志
        new_log = state.trace.log.copy()
        new_log.append(
            f"[Task_Queue] 队列长度: {len(new_queue)}, 活动任务: {active_task_id}"
        )
        new_trace = replace(state.trace, log=new_log)
        
        return replace(state, tasks=new_tasks, trace=new_trace)
    
    def _create_task_from_interrupt(self, state: BrainState) -> Optional[Task]:
        """从用户中断创建任务"""
        payload = state.hci.interrupt_payload
        target = payload.get("target", "")
        
        if not target:
            return None
        
        return Task(
            task_id=f"task_{uuid.uuid4().hex[:8]}",
            goal=f"navigate_to:{target}",
            priority=self.HIGH_PRIORITY,  # 用户直接指令优先级高
            resources_required=["base"],
            preemptible=True,
            status=TaskStatus.PENDING,
            created_at=time.time(),
            metadata={
                "source": "user_interrupt",
                "original_utterance": payload.get("original", ""),
                "target": target
            }
        )
    
    def _create_task_from_goal(self, goal_data: Dict[str, Any]) -> Optional[Task]:
        """从目标数据创建任务"""
        goal = goal_data.get("goal", "")
        if not goal:
            return None
        
        return Task(
            task_id=goal_data.get("task_id", f"task_{uuid.uuid4().hex[:8]}"),
            goal=goal,
            priority=goal_data.get("priority", self.DEFAULT_PRIORITY),
            deadline=goal_data.get("deadline"),
            resources_required=goal_data.get("resources_required", []),
            preemptible=goal_data.get("preemptible", True),
            status=TaskStatus.PENDING,
            created_at=time.time(),
            metadata=goal_data.get("metadata", {})
        )
    
    @classmethod
    def create_navigation_task(cls, target: str, priority: int = None) -> Task:
        """创建导航任务（便捷方法）"""
        return Task(
            task_id=f"nav_{uuid.uuid4().hex[:8]}",
            goal=f"navigate_to:{target}",
            priority=priority or cls.DEFAULT_PRIORITY,
            resources_required=["base"],
            preemptible=True,
            status=TaskStatus.PENDING,
            created_at=time.time(),
            metadata={"target": target, "type": "navigation"}
        )
