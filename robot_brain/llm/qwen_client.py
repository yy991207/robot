"""
通义千问 LLM 客户端实现
"""

import json
from typing import Optional

import httpx

from .config import LLMConfig, load_llm_config


class QwenLLMClient:
    """通义千问 LLM 客户端，实现 ILLMClient 协议"""
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self._config = config or load_llm_config()
    
    async def generate(self, messages: list, system_prompt: str) -> str:
        """
        调用通义千问 API 生成响应
        
        Args:
            messages: 对话消息列表
            system_prompt: 系统提示词
        
        Returns:
            LLM 生成的响应文本
        """
        # 构建请求消息
        request_messages = [{"role": "system", "content": system_prompt}]
        request_messages.extend(messages)
        
        # 构建请求体
        payload = {
            "model": self._config.model,
            "messages": request_messages,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens
        }
        
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._config.base_url}/chat/completions",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
