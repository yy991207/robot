"""
HCI_Ingress 节点

职责：接收用户输入，识别 stop/pause/new_goal 指令（简单规则匹配）
复杂指令理解和任务拆解由内环 ReAct_Decide 负责

输入：HCI 通道（CLI/Web/语音转写）
输出：更新 hci.user_utterance 和 hci.user_interrupt
"""

import re
from dataclasses import replace
from typing import Tuple

from robot_brain.core.enums import UserInterruptType
from robot_brain.core.state import BrainState, HCIState
from .base import IKernelNode


class HCIIngressNode(IKernelNode):
    """HCI 输入处理节点 - 简单规则匹配"""
    
    # 紧急停止关键词（高优先级，必须快速响应）
    STOP_KEYWORDS = ["stop", "停", "停止", "halt", "emergency", "急停", "取消"]
    PAUSE_KEYWORDS = ["pause", "暂停", "wait", "等等", "hold"]
    
    # 简单目标模式（复杂指令由ReAct处理）
    SIMPLE_GOAL_PATTERNS = [
        r"^go\s+to\s+(\w+)$",
        r"^navigate\s+to\s+(\w+)$",
        r"^去(\w+)$",
        r"^到(\w+)$",
    ]
    
    def execute(self, state: BrainState) -> BrainState:
        """处理用户输入，识别指令类型（仅简单规则）"""
        utterance = state.hci.user_utterance
        
        # 使用简单规则解析
        interrupt_type, payload = self._parse_intent(utterance)
        
        new_hci = HCIState(
            user_utterance=utterance,
            user_interrupt=interrupt_type,
            interrupt_payload=payload,
            approval_response=state.hci.approval_response
        )
        
        # 记录日志
        new_log = state.trace.log.copy()
        new_log.append(f"[HCI_Ingress] 规则匹配: {interrupt_type.value}")
        
        new_trace = replace(state.trace, log=new_log)
        return replace(state, hci=new_hci, trace=new_trace)
    
    def _parse_intent(self, utterance: str) -> Tuple[UserInterruptType, dict]:
        """解析用户意图 - 仅简单规则匹配"""
        if not utterance or not utterance.strip():
            return UserInterruptType.NONE, {}
        
        text = utterance.lower().strip()
        
        # 检查停止指令（紧急，必须快速响应）
        for keyword in self.STOP_KEYWORDS:
            if keyword in text:
                return UserInterruptType.STOP, {"original": utterance}
        
        # 检查暂停指令
        for keyword in self.PAUSE_KEYWORDS:
            if keyword in text:
                return UserInterruptType.PAUSE, {"original": utterance}
        
        # 简单目标匹配（复杂指令交给ReAct）
        for pattern in self.SIMPLE_GOAL_PATTERNS:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                target = match.group(1).strip()
                return UserInterruptType.NEW_GOAL, {
                    "original": utterance,
                    "target": target
                }
        
        # 其他输入标记为NEW_GOAL，让ReAct决定如何处理
        # 这样复杂指令如"先去厨房再去卧室"会进入ReAct
        if any(kw in text for kw in ["去", "到", "回", "导航", "前往"]):
            return UserInterruptType.NEW_GOAL, {"original": utterance}
        
        # 默认为普通输入（闲聊）
        return UserInterruptType.NONE, {"original": utterance}
    
    @classmethod
    def parse_intent(cls, utterance: str) -> Tuple[UserInterruptType, dict]:
        """类方法：解析用户意图（便于测试）"""
        node = cls()
        return node._parse_intent(utterance)
