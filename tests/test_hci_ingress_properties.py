"""
HCI_Ingress 属性测试

Feature: robot-brain-backend
Property 3: 用户指令识别正确性
Validates: Requirements 2.1, 6.1
"""

import pytest
from hypothesis import given, settings, strategies as st

from robot_brain.core.enums import UserInterruptType
from robot_brain.service.kernel.hci_ingress import HCIIngressNode


class TestHCIIngressProperties:
    """
    Property 3: 用户指令识别正确性
    For any 用户输入字符串，HCI_Ingress 节点应正确识别其意图类型（stop/pause/new_goal/normal），
    且识别结果与输入内容语义一致。
    Validates: Requirements 2.1, 6.1
    """

    @settings(max_examples=100)
    @given(keyword=st.sampled_from(HCIIngressNode.STOP_KEYWORDS))
    def test_stop_keywords_recognized(self, keyword: str):
        """包含停止关键词的输入应被识别为 STOP"""
        # 测试关键词本身
        intent, payload = HCIIngressNode.parse_intent(keyword)
        assert intent == UserInterruptType.STOP
        
        # 测试包含关键词的句子
        sentence = f"please {keyword} the robot now"
        intent, payload = HCIIngressNode.parse_intent(sentence)
        assert intent == UserInterruptType.STOP

    @settings(max_examples=100)
    @given(keyword=st.sampled_from(HCIIngressNode.PAUSE_KEYWORDS))
    def test_pause_keywords_recognized(self, keyword: str):
        """包含暂停关键词的输入应被识别为 PAUSE"""
        intent, payload = HCIIngressNode.parse_intent(keyword)
        assert intent == UserInterruptType.PAUSE

    @settings(max_examples=100)
    @given(target=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N', 'Z'))))
    def test_navigation_commands_recognized(self, target: str):
        """导航指令应被识别为 NEW_GOAL 并提取目标"""
        if not target.strip():
            return  # 跳过空白目标
        
        # 英文导航指令
        intent, payload = HCIIngressNode.parse_intent(f"go to {target}")
        assert intent == UserInterruptType.NEW_GOAL
        assert "target" in payload
        
        intent, payload = HCIIngressNode.parse_intent(f"navigate to {target}")
        assert intent == UserInterruptType.NEW_GOAL
        
        # 中文导航指令
        intent, payload = HCIIngressNode.parse_intent(f"去{target}")
        assert intent == UserInterruptType.NEW_GOAL

    @settings(max_examples=100)
    @given(text=st.text(max_size=200))
    def test_empty_or_normal_input_returns_none(self, text: str):
        """不包含特殊指令的输入应返回 NONE"""
        # 过滤掉包含关键词的文本
        lower_text = text.lower()
        has_stop = any(k in lower_text for k in HCIIngressNode.STOP_KEYWORDS)
        has_pause = any(k in lower_text for k in HCIIngressNode.PAUSE_KEYWORDS)
        has_nav = any(p.split(r'\s+')[0].replace('\\', '') in lower_text 
                      for p in ["go to", "navigate to", "去", "导航到", "前往"])
        
        if not has_stop and not has_pause and not has_nav:
            intent, _ = HCIIngressNode.parse_intent(text)
            assert intent == UserInterruptType.NONE

    def test_empty_input(self):
        """空输入应返回 NONE"""
        intent, payload = HCIIngressNode.parse_intent("")
        assert intent == UserInterruptType.NONE
        
        intent, payload = HCIIngressNode.parse_intent("   ")
        assert intent == UserInterruptType.NONE

    @settings(max_examples=100)
    @given(text=st.text(min_size=1, max_size=200))
    def test_intent_type_is_valid_enum(self, text: str):
        """识别结果必须是有效的 UserInterruptType 枚举值"""
        intent, _ = HCIIngressNode.parse_intent(text)
        assert isinstance(intent, UserInterruptType)
        assert intent in list(UserInterruptType)

    @settings(max_examples=100)
    @given(text=st.text(min_size=1, max_size=200))
    def test_payload_contains_original(self, text: str):
        """非空输入的 payload 应包含原始输入"""
        if text.strip():
            intent, payload = HCIIngressNode.parse_intent(text)
            if intent != UserInterruptType.NONE or payload:
                assert "original" in payload
