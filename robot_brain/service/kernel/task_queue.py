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

from robot_brain.core.enums import UserInterruptType, TaskStatus, Mode
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
        
        # 检测当前任务是否完成（到达目标）
        if active_task_id and state.robot.distance_to_target < 0.5:
            for task in new_queue:
                if task.task_id == active_task_id and task.status == TaskStatus.RUNNING:
                    task.status = TaskStatus.COMPLETED
                    active_task_id = None  # 清空，准备选择下一个
                    break
        
        # 处理用户中断带来的新目标
        if state.hci.user_interrupt == UserInterruptType.NEW_GOAL:
            new_tasks = self._create_task_from_interrupt(state)
            if new_tasks:
                # 用户新指令抢占所有旧任务
                new_queue = []
                new_inbox.clear()
                new_queue.extend(new_tasks)
                active_task_id = None  # 重新选择活动任务
        
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

        # EventArbitrateNode 在 TaskQueueNode 之前执行，可能把 mode 判成 IDLE。
        # 这里若已存在活动任务，则强制进入 EXEC，确保后续路由与前端响应一致。
        new_mode = state.tasks.mode
        if active_task_id:
            new_mode = Mode.EXEC
        
        new_tasks = TasksState(
            inbox=new_inbox,
            queue=new_queue,
            active_task_id=active_task_id,
            mode=new_mode,
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
    
    def _create_task_from_interrupt(self, state: BrainState) -> Optional[List[Task]]:
        """从用户中断创建任务（支持多任务）"""
        payload = state.hci.interrupt_payload
        tasks_list = []
        
        # 支持新格式（LLM 解析的多任务）
        if payload.get("tasks"):
            for i, task_data in enumerate(payload["tasks"]):
                if task_data.get("type") == "navigate":
                    target = task_data.get("target", "")
                    if target:
                        # 第一个任务优先级最高，后续递减
                        priority = self.HIGH_PRIORITY - i * 5
                        tasks_list.append(Task(
                            task_id=f"task_{uuid.uuid4().hex[:8]}",
                            goal=f"navigate_to:{target}",
                            priority=priority,
                            resources_required=["base"],
                            preemptible=True,
                            status=TaskStatus.PENDING,
                            created_at=time.time(),
                            metadata={
                                "source": "user_interrupt",
                                "original_utterance": payload.get("original", ""),
                                "target": target,
                                "sequence": i
                            }
                        ))
        
        # 兼容旧格式（单个 target）
        if not tasks_list:
            target = payload.get("target", "")
            if target:
                tasks_list.append(Task(
                    task_id=f"task_{uuid.uuid4().hex[:8]}",
                    goal=f"navigate_to:{target}",
                    priority=self.HIGH_PRIORITY,
                    resources_required=["base"],
                    preemptible=True,
                    status=TaskStatus.PENDING,
                    created_at=time.time(),
                    metadata={
                        "source": "user_interrupt",
                        "original_utterance": payload.get("original", ""),
                        "target": target
                    }
                ))
        
        return tasks_list if tasks_list else None
    
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
