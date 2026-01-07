"""
通义千问 LLM 客户端实现
"""

import json
from typing import Optional, AsyncIterator

import httpx

from .config import LLMConfig, load_llm_config


class QwenLLMClient:
    """通义千问 LLM 客户端，实现 ILLMClient 协议"""
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self._config = config or load_llm_config()
    
    async def generate(self, messages: list, system_prompt: str) -> str:
        """
        调用通义千问 API 生成响应（非流式）
        """
        result = []
        async for chunk in self.generate_stream(messages, system_prompt):
            result.append(chunk)
        return "".join(result)
    
    async def generate_stream(self, messages: list, system_prompt: str) -> AsyncIterator[str]:
        """
        流式调用通义千问 API
        """
        request_messages = [{"role": "system", "content": system_prompt}]
        request_messages.extend(messages)
        
        payload = {
            "model": self._config.model,
            "messages": request_messages,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "stream": True
        }
        
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self._config.base_url}/chat/completions",
                json=payload,
                headers=headers
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
