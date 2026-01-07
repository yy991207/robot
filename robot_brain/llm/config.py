"""
LLM 配置加载模块
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class LLMConfig:
    """LLM 配置"""
    api_key: str
    base_url: str
    model: str = "qwen-plus"
    temperature: float = 0.7
    max_tokens: int = 2048


def load_llm_config(config_path: Optional[str] = None) -> LLMConfig:
    """
    从配置文件加载 LLM 配置
    
    Args:
        config_path: 配置文件路径，默认为 config/config.yaml
    
    Returns:
        LLMConfig 实例
    """
    if config_path is None:
        # 默认配置路径
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "config" / "config.yaml"
    
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)
    
    alibaba_config = config_data.get("alibaba", {})
    
    return LLMConfig(
        api_key=alibaba_config.get("key", ""),
        base_url=alibaba_config.get("base_url", ""),
        model=alibaba_config.get("model", "qwen-plus"),
        temperature=alibaba_config.get("temperature", 0.7),
        max_tokens=alibaba_config.get("max_tokens", 2048)
    )
