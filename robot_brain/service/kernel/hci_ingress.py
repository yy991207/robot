"""
HCI_Ingress 节点

职责：接收用户输入，识别 stop/pause/new_goal 指令
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
    """HCI 输入处理节点"""
    
    # 指令关键词映射
    STOP_KEYWORDS = ["stop", "停止", "halt", "emergency", "急停", "取消"]
    PAUSE_KEYWORDS = ["pause", "暂停", "wait", "等等", "hold"]
    NEW_GOAL_PATTERNS = [
        r"go\s+to\s+(.+)",
        r"navigate\s+to\s+(.+)",
        r"去(.+)",
        r"导航到(.+)",
        r"前往(.+)",
    ]
    
    def execute(self, state: BrainState) -> BrainState:
        """处理用户输入，识别指令类型"""
        utterance = state.hci.user_utterance
        interrupt_type, payload = self._parse_intent(utterance)
        
        new_hci = HCIState(
            user_utterance=utterance,
            user_interrupt=interrupt_type,
            interrupt_payload=payload,
            approval_response=state.hci.approval_response
        )
        
        # 记录日志
        new_log = state.trace.log.copy()
        new_log.append(f"[HCI_Ingress] 识别用户意图: {interrupt_type.value}, payload: {payload}")
        
        new_trace = replace(state.trace, log=new_log)
        return replace(state, hci=new_hci, trace=new_trace)
    
    def _parse_intent(self, utterance: str) -> Tuple[UserInterruptType, dict]:
        """解析用户意图"""
        if not utterance or not utterance.strip():
            return UserInterruptType.NONE, {}
        
        text = utterance.lower().strip()
        
        # 检查停止指令
        for keyword in self.STOP_KEYWORDS:
            if keyword in text:
                return UserInterruptType.STOP, {"original": utterance}
        
        # 检查暂停指令
        for keyword in self.PAUSE_KEYWORDS:
            if keyword in text:
                return UserInterruptType.PAUSE, {"original": utterance}
        
        # 检查新目标指令
        for pattern in self.NEW_GOAL_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                target = match.group(1).strip()
                return UserInterruptType.NEW_GOAL, {
                    "original": utterance,
                    "target": target
                }
        
        # 默认为普通输入（无中断）
        return UserInterruptType.NONE, {"original": utterance}
    
    @classmethod
    def parse_intent(cls, utterance: str) -> Tuple[UserInterruptType, dict]:
        """类方法：解析用户意图（便于测试）"""
        node = cls()
        return node._parse_intent(utterance)
