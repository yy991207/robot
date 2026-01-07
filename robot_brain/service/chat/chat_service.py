"""
对话服务

处理非指令类的闲聊对话，支持对话历史持久化
"""

from typing import List, Dict, Any, Optional, AsyncIterator, TYPE_CHECKING

from robot_brain.service.react.react_decide import ILLMClient

if TYPE_CHECKING:
    from robot_brain.persistence.sqlite_checkpointer import SQLiteCheckpointer


class ChatService:
    """对话服务"""
    
    SYSTEM_PROMPT = """你是一个友好的家用服务机器人助手。
你可以帮助用户完成导航、语音通知等任务。
当用户和你闲聊时，请友好地回应。
如果用户想让你做什么事情，可以提示他们使用指令，比如"去厨房"、"导航到客厅"等。
保持回复简洁友好。"""
    
    def __init__(
        self,
        llm_client: ILLMClient,
        checkpointer: Optional["SQLiteCheckpointer"] = None,
        thread_id: str = "chat_default"
    ):
        self._llm = llm_client
        self._checkpointer = checkpointer
        self._thread_id = thread_id
        self._history: List[Dict[str, str]] = []
        self._max_history = 10
        self._initialized = False
    
    async def _ensure_initialized(self):
        """确保从持久化加载历史"""
        if self._initialized:
            return
        
        if self._checkpointer:
            self._history = await self._checkpointer.load_chat_history(self._thread_id, self._max_history)
        
        self._initialized = True
    
    async def chat(self, user_input: str) -> str:
        """非流式对话"""
        await self._ensure_initialized()
        
        self._history.append({"role": "user", "content": user_input})
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        
        # 持久化用户消息
        if self._checkpointer:
            await self._checkpointer.save_chat_message(self._thread_id, "user", user_input)
        
        response = await self._llm.generate(self._history, self.SYSTEM_PROMPT)
        self._history.append({"role": "assistant", "content": response})
        
        # 持久化助手回复
        if self._checkpointer:
            await self._checkpointer.save_chat_message(self._thread_id, "assistant", response)
        
        return response
    
    async def chat_stream(self, user_input: str) -> AsyncIterator[str]:
        """流式对话"""
        await self._ensure_initialized()
        
        self._history.append({"role": "user", "content": user_input})
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        
        # 持久化用户消息
        if self._checkpointer:
            await self._checkpointer.save_chat_message(self._thread_id, "user", user_input)
        
        full_response = []
        async for chunk in self._llm.generate_stream(self._history, self.SYSTEM_PROMPT):
            full_response.append(chunk)
            yield chunk
        
        response = "".join(full_response)
        self._history.append({"role": "assistant", "content": response})
        
        # 持久化助手回复
        if self._checkpointer:
            await self._checkpointer.save_chat_message(self._thread_id, "assistant", response)
    
    async def clear_history(self):
        """清空对话历史"""
        self._history.clear()
        if self._checkpointer:
            await self._checkpointer.clear_chat_history(self._thread_id)
    
    def get_history(self) -> List[Dict[str, str]]:
        """获取对话历史"""
        return self._history.copy()
