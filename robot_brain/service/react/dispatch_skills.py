"""
Dispatch_Skills 节点

职责：执行取消/派发（ROS2 action/service 调用），记录 running handle
输入：react.proposed_ops.to_cancel, to_dispatch
输出：skills.running, trace.log

注意：这是唯一允许产生物理副作用的节点
"""

import time
import uuid
from dataclasses import replace
from typing import Dict, Any, List, Optional, Protocol

from robot_brain.core.models import RunningSkill, SkillResult
from robot_brain.core.enums import SkillStatus
from robot_brain.core.state import BrainState, SkillsState
from .base import IReActNode


class ISkillExecutor(Protocol):
    """技能执行器接口"""
    
    async def dispatch(self, skill_name: str, params: Dict[str, Any]) -> str:
        """派发技能，返回 goal_id"""
        ...
    
    async def cancel(self, goal_id: str) -> bool:
        """取消技能"""
        ...


class MockSkillExecutor:
    """模拟技能执行器"""
    
    def __init__(self):
        self._dispatched = []
        self._cancelled = []
    
    async def dispatch(self, skill_name: str, params: Dict[str, Any]) -> str:
        goal_id = f"goal_{uuid.uuid4().hex[:8]}"
        self._dispatched.append({"goal_id": goal_id, "skill_name": skill_name, "params": params})
        return goal_id
    
    async def cancel(self, goal_id: str) -> bool:
        self._cancelled.append(goal_id)
        return True
    
    def get_dispatched(self) -> List[Dict]:
        return self._dispatched
    
    def get_cancelled(self) -> List[str]:
        return self._cancelled


class DispatchSkillsNode(IReActNode):
    """技能派发节点"""
    
    def __init__(self, executor: Optional[ISkillExecutor] = None):
        self._executor = executor or MockSkillExecutor()
    
    async def execute(self, state: BrainState) -> BrainState:
        """执行技能取消和派发"""
        proposed_ops = state.react.proposed_ops
        if not proposed_ops:
            return state
        
        new_running = list(state.skills.running)
        new_log = state.trace.log.copy()
        
        # 1. 执行取消
        for goal_id in proposed_ops.to_cancel:
            success = await self._executor.cancel(goal_id)
            if success:
                # 从 running 中移除
                new_running = [s for s in new_running if s.goal_id != goal_id]
                new_log.append(f"[Dispatch_Skills] 取消技能: {goal_id}")
        
        # 2. 执行派发
        for dispatch in proposed_ops.to_dispatch:
            skill_name = dispatch.get("skill_name", "")
            params = dispatch.get("params", {})
            
            if not skill_name:
                continue
            
            # 获取技能定义
            skill_def = state.skills.registry.get(skill_name)
            timeout_s = skill_def.timeout_s if skill_def else 60.0
            resources = skill_def.resources_required if skill_def else []
            
            # 派发技能
            goal_id = await self._executor.dispatch(skill_name, params)
            
            # 记录运行中的技能
            running_skill = RunningSkill(
                goal_id=goal_id,
                skill_name=skill_name,
                start_time=time.time(),
                timeout_s=timeout_s,
                resources_occupied=resources,
                params=params
            )
            new_running.append(running_skill)
            new_log.append(f"[Dispatch_Skills] 派发技能: {skill_name} -> {goal_id}")
        
        # 3. 更新资源状态
        new_resources = state.robot.resources.copy()
        occupied_resources = set()
        for skill in new_running:
            occupied_resources.update(skill.resources_occupied)
        
        for resource in ["base", "arm", "gripper"]:
            new_resources[f"{resource}_busy"] = resource in occupied_resources
        
        new_robot = replace(state.robot, resources=new_resources)
        new_skills = SkillsState(
            registry=state.skills.registry,
            running=new_running,
            last_result=state.skills.last_result
        )
        new_trace = replace(state.trace, log=new_log)
        
        return replace(state, skills=new_skills, robot=new_robot, trace=new_trace)
