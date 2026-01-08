"""
Build_Observation 节点

职责：把"世界+机器人客观状态+任务+技能结果"压缩成结构化 observation
输入：world.summary, robot.*, tasks.*, skills.*
输出：react.observation, messages, react.iter
"""

from dataclasses import replace
from typing import Dict, Any, List

from robot_brain.core.state import BrainState, ReactState
from .base import IReActNode


class BuildObservationNode(IReActNode):
    """构建观测节点"""
    
    async def execute(self, state: BrainState) -> BrainState:
        """构建结构化观测"""
        observation = self._build_observation(state)
        
        # 更新 react 状态
        new_react = ReactState(
            iter=state.react.iter + 1,
            observation=observation,
            decision=state.react.decision,
            proposed_ops=state.react.proposed_ops,
            stop_reason=state.react.stop_reason
        )
        
        # 添加观测到 messages
        new_messages = list(state.messages)
        new_messages.append({
            "role": "system",
            "content": self._format_observation_message(observation),
            "type": "observation"
        })
        
        # 记录日志
        new_log = state.trace.log.copy()
        new_log.append(f"[Build_Observation] 迭代: {new_react.iter}")
        new_trace = replace(state.trace, log=new_log)
        
        return replace(state, react=new_react, messages=new_messages, trace=new_trace)
    
    def _build_observation(self, state: BrainState) -> Dict[str, Any]:
        """构建观测数据"""
        # 获取活动任务信息
        active_task = None
        for task in state.tasks.queue:
            if task.task_id == state.tasks.active_task_id:
                active_task = task
                break

        obstacles_risk_count = 0
        for obs in state.world.obstacles:
            if obs.get("collision_risk") is True:
                obstacles_risk_count += 1

        queue_preview = []
        for t in state.tasks.queue:
            queue_preview.append({
                "task_id": t.task_id,
                "goal": t.goal,
                "status": t.status.value,
                "metadata": {
                    "source": t.metadata.get("source"),
                    "sequence": t.metadata.get("sequence")
                }
            })
        
        observation = {
            "iteration": state.react.iter + 1,
            "world": {
                "summary": state.world.summary,
                "zones": state.world.zones,
                "obstacle_count": len(state.world.obstacles),
                "obstacles_risk_count": obstacles_risk_count
            },
            "robot": {
                "position": {
                    "x": round(state.robot.pose.x, 2),
                    "y": round(state.robot.pose.y, 2)
                },
                "home_pose": {
                    "x": round(state.robot.home_pose.x, 2),
                    "y": round(state.robot.home_pose.y, 2)
                },
                "battery_pct": round(state.robot.battery_pct, 1),
                "battery_state": state.robot.battery_state,
                "distance_to_target": round(state.robot.distance_to_target, 2),
                "resources": state.robot.resources
            },
            "task": {
                "active_task_id": state.tasks.active_task_id,
                "goal": active_task.goal if active_task else None,
                "queue_length": len(state.tasks.queue),
                "queue_preview": queue_preview,
                "mode": state.tasks.mode.value
            },
            "skills": {
                "running_count": len(state.skills.running),
                "running": [
                    {"skill_name": s.skill_name, "goal_id": s.goal_id}
                    for s in state.skills.running
                ],
                "last_result": None
            }
        }
        
        # 添加上次技能执行结果
        if state.skills.last_result:
            observation["skills"]["last_result"] = {
                "status": state.skills.last_result.status.value,
                "error_code": state.skills.last_result.error_code,
                "error_msg": state.skills.last_result.error_msg
            }
        
        return observation
    
    def _format_observation_message(self, observation: Dict[str, Any]) -> str:
        """格式化观测为消息文本"""
        parts = [f"[Observation - Iteration {observation['iteration']}]"]
        
        # 世界状态
        world = observation["world"]
        parts.append(f"World: {world['summary']}")
        
        # 机器人状态
        robot = observation["robot"]
        parts.append(
            f"Robot: pos=({robot['position']['x']}, {robot['position']['y']}), "
            f"battery={robot['battery_pct']}%, "
            f"distance_to_target={robot['distance_to_target']}m"
        )
        
        # 任务状态
        task = observation["task"]
        if task["active_task_id"]:
            parts.append(f"Task: {task['goal']} (mode={task['mode']})")
        else:
            parts.append(f"Task: None (mode={task['mode']})")
        
        # 技能状态
        skills = observation["skills"]
        if skills["running"]:
            running_names = [s["skill_name"] for s in skills["running"]]
            parts.append(f"Running skills: {', '.join(running_names)}")
        
        if skills["last_result"]:
            result = skills["last_result"]
            parts.append(f"Last result: {result['status']}")
            if result["error_code"]:
                parts.append(f"  Error: {result['error_code']} - {result['error_msg']}")
        
        return "\n".join(parts)
