"""
ReAct_Decide 属性测试

Feature: robot-brain-backend
Property 7: 决策类型完备性
Validates: Requirements 3.2, 3.9
"""

import json
import pytest
from hypothesis import given, settings, strategies as st

from robot_brain.core.enums import DecisionType
from robot_brain.core.models import Decision
from robot_brain.service.react.react_decide import ReActDecideNode


class TestDecisionTypeCompleteness:
    """
    Property 7: 决策类型完备性
    For any ReAct_Decide 节点的输出，其决策类型必须是
    CONTINUE、REPLAN、RETRY、SWITCH_TASK、ASK_HUMAN、FINISH、ABORT 之一。
    Validates: Requirements 3.2, 3.9
    """

    @settings(max_examples=100)
    @given(decision_type=st.sampled_from([
        "CONTINUE", "REPLAN", "RETRY", "SWITCH_TASK", 
        "ASK_HUMAN", "FINISH", "ABORT"
    ]))
    def test_valid_decision_types_parsed_correctly(self, decision_type: str):
        """有效的决策类型应被正确解析"""
        node = ReActDecideNode()
        response = json.dumps({
            "type": decision_type,
            "reason": "test reason",
            "ops": []
        })
        
        decision = node._parse_decision(response)
        assert isinstance(decision, Decision)
        assert decision.type == DecisionType(decision_type)

    @settings(max_examples=100)
    @given(invalid_type=st.text(min_size=1, max_size=20).filter(
        lambda x: x not in ["CONTINUE", "REPLAN", "RETRY", "SWITCH_TASK", 
                           "ASK_HUMAN", "FINISH", "ABORT"]
    ))
    def test_invalid_decision_type_falls_back_to_ask_human(self, invalid_type: str):
        """无效的决策类型应回退到 ASK_HUMAN"""
        node = ReActDecideNode()
        response = json.dumps({
            "type": invalid_type,
            "reason": "test",
            "ops": []
        })
        
        decision = node._parse_decision(response)
        assert isinstance(decision, Decision)
        # 无效类型会导致 ValueError，回退到 ASK_HUMAN
        assert decision.type == DecisionType.ASK_HUMAN

    @settings(max_examples=100)
    @given(reason=st.text(max_size=200))
    def test_decision_reason_preserved(self, reason: str):
        """决策原因应被保留"""
        node = ReActDecideNode()
        response = json.dumps({
            "type": "CONTINUE",
            "reason": reason,
            "ops": []
        })
        
        decision = node._parse_decision(response)
        assert decision.reason == reason

    @settings(max_examples=100)
    @given(ops=st.lists(
        st.fixed_dictionaries({
            "skill": st.text(min_size=1, max_size=50),
            "params": st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50), max_size=3)
        }),
        max_size=5
    ))
    def test_decision_ops_preserved(self, ops: list):
        """决策操作应被保留"""
        node = ReActDecideNode()
        response = json.dumps({
            "type": "CONTINUE",
            "reason": "test",
            "ops": ops
        })
        
        decision = node._parse_decision(response)
        assert decision.ops == ops

    def test_malformed_json_falls_back_to_ask_human(self):
        """格式错误的 JSON 应回退到 ASK_HUMAN"""
        node = ReActDecideNode()
        
        # 完全无效的响应
        decision = node._parse_decision("not json at all")
        assert decision.type == DecisionType.ASK_HUMAN
        
        # 部分有效但缺少必要字段
        decision = node._parse_decision('{"incomplete": true}')
        assert decision.type == DecisionType.ASK_HUMAN

    def test_json_embedded_in_text_extracted(self):
        """嵌入在文本中的 JSON 应被提取"""
        node = ReActDecideNode()
        response = '''
        Based on the observation, I decide:
        {"type": "FINISH", "reason": "Task completed", "ops": []}
        That's my decision.
        '''
        
        decision = node._parse_decision(response)
        assert decision.type == DecisionType.FINISH
        assert decision.reason == "Task completed"

    @settings(max_examples=100)
    @given(decision_type=st.sampled_from(list(DecisionType)))
    def test_all_decision_types_are_valid_enum_values(self, decision_type: DecisionType):
        """所有 DecisionType 枚举值都应是有效的"""
        assert decision_type.value in [
            "CONTINUE", "REPLAN", "RETRY", "SWITCH_TASK",
            "ASK_HUMAN", "FINISH", "ABORT"
        ]
