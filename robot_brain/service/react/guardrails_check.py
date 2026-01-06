"""
Guardrails_Check 节点

职责：硬护栏与资源检查
- 技能存在性检查
- 参数 schema 验证
- 资源冲突检测
输入：react.proposed_ops, skills.registry, robot.resources, tasks.mode
输出：验证后的操作或拒绝
"""

from dataclasses import replace
from typing import List, Dict, Any, Tuple, Optional

from robot_brain.core.enums import DecisionType, SkillStatus
from robot_brain.core.models import ProposedOps, SkillResult, Decision
from robot_brain.core.state import BrainState, ReactState
from .base import IReActNode


class GuardrailsCheckNode(IReActNode):
    """护栏检查节点"""
    
    async def execute(self, state: BrainState) -> BrainState:
        """执行护栏检查"""
        proposed_ops = state.react.proposed_ops
        if not proposed_ops:
            return state
        
        # 执行检查
        validated_ops, errors = self._validate(state, proposed_ops)
        
        new_react = state.react
        new_skills = state.skills
        
        if errors:
            # 有错误：更新决策为 REPLAN 或 ASK_HUMAN
            error_msg = "; ".join(errors)
            new_decision = Decision(
                type=DecisionType.ASK_HUMAN if len(errors) > 2 else DecisionType.REPLAN,
                reason=f"Guardrails check failed: {error_msg}",
                ops=[]
            )
            new_react = ReactState(
                iter=state.react.iter,
                observation=state.react.observation,
                decision=new_decision,
                proposed_ops=validated_ops,
                stop_reason=state.react.stop_reason
            )
            
            # 记录失败结果
            new_last_result = SkillResult(
                status=SkillStatus.FAILED,
                error_code="GUARDRAILS_FAILED",
                error_msg=error_msg
            )
            new_skills = replace(state.skills, last_result=new_last_result)
        else:
            # 检查通过：更新 proposed_ops
            new_react = ReactState(
                iter=state.react.iter,
                observation=state.react.observation,
                decision=state.react.decision,
                proposed_ops=validated_ops,
                stop_reason=state.react.stop_reason
            )
        
        # 记录日志
        new_log = state.trace.log.copy()
        if errors:
            new_log.append(f"[Guardrails_Check] 失败: {errors}")
        else:
            new_log.append(f"[Guardrails_Check] 通过")
        new_trace = replace(state.trace, log=new_log)
        
        return replace(state, react=new_react, skills=new_skills, trace=new_trace)
    
    def _validate(self, state: BrainState, ops: ProposedOps) -> Tuple[ProposedOps, List[str]]:
        """验证操作"""
        errors = []
        valid_dispatches = []
        
        for dispatch in ops.to_dispatch:
            skill_name = dispatch.get("skill_name", "")
            params = dispatch.get("params", {})
            
            # 1. 检查技能存在性
            if skill_name not in state.skills.registry:
                errors.append(f"Skill not found: {skill_name}")
                continue
            
            skill_def = state.skills.registry[skill_name]
            
            # 2. 检查参数 schema
            param_error = self._validate_params(skill_def.args_schema, params)
            if param_error:
                errors.append(f"Invalid params for {skill_name}: {param_error}")
                continue
            
            # 3. 检查资源冲突
            conflict = self._check_resource_conflict(
                skill_def.resources_required,
                state.robot.resources,
                state.skills.running
            )
            if conflict:
                errors.append(f"Resource conflict for {skill_name}: {conflict}")
                continue
            
            valid_dispatches.append(dispatch)
        
        validated_ops = ProposedOps(
            to_cancel=ops.to_cancel,
            to_dispatch=valid_dispatches,
            to_speak=ops.to_speak,
            need_approval=ops.need_approval,
            approval_payload=ops.approval_payload
        )
        
        return validated_ops, errors
    
    def _validate_params(self, schema: Dict[str, Any], params: Dict[str, Any]) -> Optional[str]:
        """验证参数（简化实现）"""
        if not schema:
            return None
        
        # 检查必需参数
        required = schema.get("required", [])
        for field in required:
            if field not in params:
                return f"Missing required field: {field}"
        
        return None
    
    def _check_resource_conflict(
        self,
        required: List[str],
        current_resources: Dict[str, bool],
        running_skills: List
    ) -> Optional[str]:
        """检查资源冲突"""
        # 检查当前资源状态
        for resource in required:
            resource_key = f"{resource}_busy"
            if current_resources.get(resource_key, False):
                return f"Resource {resource} is busy"
        
        # 检查运行中技能占用的资源
        occupied = set()
        for skill in running_skills:
            occupied.update(skill.resources_occupied)
        
        for resource in required:
            if resource in occupied:
                return f"Resource {resource} is occupied by running skill"
        
        return None
    
    @classmethod
    def check_resource_conflict(
        cls,
        required: List[str],
        current_resources: Dict[str, bool],
        running_skills: List
    ) -> Optional[str]:
        """类方法：检查资源冲突（便于测试）"""
        node = cls()
        return node._check_resource_conflict(required, current_resources, running_skills)
