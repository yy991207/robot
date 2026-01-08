"""
LLM 意图解析器

使用 LLM 理解用户意图，支持：
- 复杂任务识别和拆解
- 上下文理解（指代消解）
- 记忆查询（从 checkpoint 获取历史）
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from robot_brain.core.enums import UserInterruptType
from robot_brain.service.react.react_decide import ILLMClient


@dataclass
class ParsedIntent:
    """解析后的意图"""
    intent_type: UserInterruptType
    tasks: List[Dict[str, Any]]  # 拆解后的任务列表
    response: str  # 给用户的回复
    raw_output: str  # LLM 原始输出


class LLMIntentParser:
    """LLM 意图解析器"""
    
    SYSTEM_PROMPT = """你是一个家用服务机器人的意图解析器。

你的任务是理解用户的指令，并将其转换为结构化的任务。

## 可用区域
- kitchen (厨房)
- living_room (客厅)  
- bedroom (卧室)
- bathroom (浴室/洗手间/卫生间)
- charging_station (充电站)

## 可用技能
- NavigateToPose: 导航到指定位置
- Speak: 语音播报
- StopBase: 停止移动

## 意图类型
- STOP: 停止当前任务（关键词：停、停止、取消、别动）
- PAUSE: 暂停当前任务（关键词：暂停、等等、等一下）
- NEW_GOAL: 新的导航/任务目标
- NONE: 闲聊，不是指令

## 输出格式（JSON）
{
  "intent_type": "STOP|PAUSE|NEW_GOAL|NONE",
  "tasks": [
    {"type": "navigate", "target": "区域英文名"},
    {"type": "speak", "content": "要说的话"}
  ],
  "response": "给用户的简短回复",
  "reasoning": "你的推理过程"
}

## 示例

用户: "去厨房"
输出: {"intent_type": "NEW_GOAL", "tasks": [{"type": "navigate", "target": "kitchen"}], "response": "好的，正在前往厨房", "reasoning": "用户要求导航到厨房"}

用户: "回来" 或 "回去充电"
输出: {"intent_type": "NEW_GOAL", "tasks": [{"type": "navigate", "target": "charging_station"}], "response": "好的，正在返回充电站", "reasoning": "回来通常指返回充电站"}

用户: "先去厨房再去卧室"
输出: {"intent_type": "NEW_GOAL", "tasks": [{"type": "navigate", "target": "kitchen"}, {"type": "navigate", "target": "bedroom"}], "response": "好的，先去厨房，然后去卧室", "reasoning": "用户要求依次访问两个地点"}

用户: "停"
输出: {"intent_type": "STOP", "tasks": [], "response": "已停止", "reasoning": "用户要求停止"}

用户: "你好"
输出: {"intent_type": "NONE", "tasks": [], "response": "", "reasoning": "这是闲聊，不是指令"}

## 注意
1. 理解语义，不要死板匹配关键词
2. "回来"、"回去"、"回家" 都指返回充电站
3. 复合任务要拆解成多个子任务
4. 只输出 JSON，不要其他内容"""

    def __init__(self, llm_client: ILLMClient):
        self._llm = llm_client
    
    async def parse(
        self,
        utterance: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ParsedIntent:
        """解析用户意图"""
        user_msg = f"用户输入: {utterance}"
        
        if context:
            user_msg += f"\n\n当前上下文:\n"
            if context.get("robot_position"):
                pos = context["robot_position"]
                user_msg += f"- 机器人位置: ({pos['x']:.1f}, {pos['y']:.1f})\n"
            if context.get("current_zone"):
                user_msg += f"- 当前区域: {context['current_zone']}\n"
            if context.get("active_task"):
                user_msg += f"- 当前任务: {context['active_task']}\n"
            if context.get("recent_history"):
                user_msg += f"- 最近对话:\n"
                for msg in context["recent_history"][-3:]:
                    user_msg += f"  [{msg['role']}] {msg['content']}\n"
        
        messages = [{"role": "user", "content": user_msg}]
        
        try:
            response = await self._llm.generate(messages, self.SYSTEM_PROMPT)
            return self._parse_response(response, utterance)
        except Exception as e:
            return self._fallback_parse(utterance, str(e))
    
    def _parse_response(self, response: str, utterance: str) -> ParsedIntent:
        """解析 LLM 响应"""
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            data = json.loads(response)
            
            intent_type = UserInterruptType(data.get("intent_type", "NONE"))
            tasks = data.get("tasks", [])
            resp = data.get("response", "")
            
            return ParsedIntent(
                intent_type=intent_type,
                tasks=tasks,
                response=resp,
                raw_output=response
            )
        except Exception as e:
            return self._fallback_parse(utterance, str(e))
    
    def _fallback_parse(self, utterance: str, error: str = "") -> ParsedIntent:
        """回退解析（简单规则匹配）"""
        text = utterance.lower().strip()
        
        if any(kw in text for kw in ["停", "stop", "取消", "别动"]):
            return ParsedIntent(
                intent_type=UserInterruptType.STOP,
                tasks=[],
                response="已停止",
                raw_output=f"fallback: {error}"
            )
        
        if any(kw in text for kw in ["暂停", "等等", "pause"]):
            return ParsedIntent(
                intent_type=UserInterruptType.PAUSE,
                tasks=[],
                response="已暂停",
                raw_output=f"fallback: {error}"
            )
        
        if any(kw in text for kw in ["回来", "回去", "回家", "充电"]):
            return ParsedIntent(
                intent_type=UserInterruptType.NEW_GOAL,
                tasks=[{"type": "navigate", "target": "charging_station"}],
                response="好的，正在返回充电站",
                raw_output=f"fallback: {error}"
            )
        
        zone_map = {
            "厨房": "kitchen", "kitchen": "kitchen",
            "客厅": "living_room", "living": "living_room",
            "卧室": "bedroom", "bedroom": "bedroom",
            "浴室": "bathroom", "洗手间": "bathroom", "卫生间": "bathroom",
        }
        for cn, en in zone_map.items():
            if cn in text:
                return ParsedIntent(
                    intent_type=UserInterruptType.NEW_GOAL,
                    tasks=[{"type": "navigate", "target": en}],
                    response=f"好的，正在前往{cn}",
                    raw_output=f"fallback: {error}"
                )
        
        return ParsedIntent(
            intent_type=UserInterruptType.NONE,
            tasks=[],
            response="",
            raw_output=f"fallback: {error}"
        )
    
    def to_interrupt_payload(self, parsed: ParsedIntent) -> Tuple[UserInterruptType, Dict[str, Any]]:
        """转换为 HCI 中断格式"""
        payload = {
            "tasks": parsed.tasks,
            "response": parsed.response
        }
        
        if parsed.tasks and parsed.tasks[0].get("type") == "navigate":
            payload["target"] = parsed.tasks[0]["target"]
        
        return parsed.intent_type, payload
