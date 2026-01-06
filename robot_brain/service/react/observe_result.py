"""
Observe_Result 节点

职责：收集技能 feedback/result，结构化写回
输入：ROS2 action feedback/result, skills.running
输出：skills.running, skills.last_result, messages
"""

import time
from dataclasses import replace
from typing import Dict, Any, List, Optional, Protocol

from robot_brain.core.enums import SkillStatus
from robot_brain.core.models import RunningSkill, SkillResult
from robot_brain.core.state import BrainState, SkillsState
from .base import IReActNode


class IResultObserver(Protocol):
    """结果观察器接口"""
    
    async def get_feedback(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """获取技能反馈"""
        ...
    
    async def get_result(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """获取技能结果"""
        ...
    
    async def is_done(self, goal_id: str) -> bool:
        """检查技能是否完成"""
        ...


class MockResultObserver:
    """模拟结果观察器"""
    
    def __init__(self):
        self._results = {}
        self._feedbacks = {}
        self._done = set()
    
    def set_result(self, goal_id: str, result: Dict[str, Any]):
        self._results[goal_id] = result
        self._done.add(goal_id)
    
    def set_feedback(self, goal_id: str, feedback: Dict[str, Any]):
        self._feedbacks[goal_id] = feedback
    
    async def get_feedback(self, goal_id: str) -> Optional[Dict[str, Any]]:
        return self._feedbacks.get(goal_id)
    
    async def get_result(self, goal_id: str) -> Optional[Dict[str, Any]]:
        return self._results.get(goal_id)
    
    async def is_done(self, goal_id: str) -> bool:
        return goal_id in self._done


class ObserveResultNode(IReActNode):
    """观察执行结果节点"""
    
    def __init__(self, observer: Optional[IResultObserver] = None):
        self._observer = observer or MockResultObserver()
    
    async def execute(self, state: BrainState) -> BrainState:
        """收集技能执行结果"""
        new_running = []
        completed_results = []
        new_log = state.trace.log.copy()
        
        for skill in state.skills.running:
            # 检查是否完成
            is_done = await self._observer.is_done(skill.goal_id)
            
            if is_done:
                # 获取结果
                result_data = await self._observer.get_result(skill.goal_id)
                result = self._parse_result(result_data)
                completed_results.append(result)
                new_log.append(
                    f"[Observe_Result] 技能完成: {skill.skill_name} -> {result.status.value}"
                )
            else:
                # 检查超时
                elapsed = time.time() - skill.start_time
                if elapsed > skill.timeout_s:
                    result = SkillResult(
                        status=SkillStatus.FAILED,
                        error_code="TIMEOUT",
                        error_msg=f"Skill {skill.skill_name} timed out after {skill.timeout_s}s"
                    )
                    completed_results.append(result)
                    new_log.append(f"[Observe_Result] 技能超时: {skill.skill_name}")
                else:
                    # 获取反馈
                    feedback = await self._observer.get_feedback(skill.goal_id)
                    if feedback:
                        new_log.append(
                            f"[Observe_Result] 技能反馈: {skill.skill_name} - {feedback}"
                        )
                    new_running.append(skill)
        
        # 更新最后结果
        last_result = state.skills.last_result
        if completed_results:
            last_result = completed_results[-1]
        
        # 更新资源状态
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
            last_result=last_result
        )
        
        # 添加结果到 messages
        new_messages = list(state.messages)
        if completed_results:
            for result in completed_results:
                new_messages.append({
                    "role": "system",
                    "content": f"Skill result: {result.status.value}",
                    "type": "tool_result",
                    "result": {
                        "status": result.status.value,
                        "error_code": result.error_code,
                        "error_msg": result.error_msg,
                        "metrics": result.metrics
                    }
                })
        
        new_trace = replace(state.trace, log=new_log)
        
        return replace(
            state,
            skills=new_skills,
            robot=new_robot,
            messages=new_messages,
            trace=new_trace
        )
    
    def _parse_result(self, result_data: Optional[Dict[str, Any]]) -> SkillResult:
        """解析结果数据"""
        if not result_data:
            return SkillResult(status=SkillStatus.SUCCESS)
        
        status_str = result_data.get("status", "SUCCESS")
        try:
            status = SkillStatus(status_str)
        except ValueError:
            status = SkillStatus.SUCCESS if status_str == "success" else SkillStatus.FAILED
        
        return SkillResult(
            status=status,
            error_code=result_data.get("error_code", ""),
            error_msg=result_data.get("error_msg", ""),
            metrics=result_data.get("metrics", {})
        )
