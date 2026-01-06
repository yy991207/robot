"""
日志配置

配置 trace.log 记录
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


class TraceFormatter(logging.Formatter):
    """Trace 日志格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        # 添加时间戳
        record.timestamp = datetime.now().isoformat()
        return super().format(record)


def setup_logging(
    level: int = logging.INFO,
    log_dir: str = "logs",
    enable_file_logging: bool = True,
    enable_console_logging: bool = True
) -> logging.Logger:
    """
    设置日志配置
    
    Args:
        level: 日志级别
        log_dir: 日志目录
        enable_file_logging: 是否启用文件日志
        enable_console_logging: 是否启用控制台日志
    
    Returns:
        根日志记录器
    """
    # 创建根日志记录器
    root_logger = logging.getLogger("robot_brain")
    root_logger.setLevel(level)
    
    # 清除已有处理器
    root_logger.handlers.clear()
    
    # 日志格式
    log_format = "%(timestamp)s [%(levelname)s] %(name)s: %(message)s"
    formatter = TraceFormatter(log_format)
    
    # 控制台处理器
    if enable_console_logging:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # 文件处理器
    if enable_file_logging:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        # 主日志文件
        main_log_file = log_path / "robot_brain.log"
        file_handler = logging.FileHandler(main_log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # Trace 日志文件（详细记录）
        trace_log_file = log_path / "trace.log"
        trace_handler = logging.FileHandler(trace_log_file, encoding="utf-8")
        trace_handler.setLevel(logging.DEBUG)
        trace_handler.setFormatter(TraceFormatter(
            "%(timestamp)s [%(levelname)s] %(name)s [%(funcName)s:%(lineno)d]: %(message)s"
        ))
        root_logger.addHandler(trace_handler)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """获取日志记录器"""
    return logging.getLogger(f"robot_brain.{name}")


class TraceLogger:
    """Trace 日志记录器"""
    
    def __init__(self, name: str):
        self._logger = get_logger(name)
    
    def trace_node_enter(self, node_name: str, state_summary: str):
        """记录节点进入"""
        self._logger.debug(f"ENTER {node_name}: {state_summary}")
    
    def trace_node_exit(self, node_name: str, state_summary: str):
        """记录节点退出"""
        self._logger.debug(f"EXIT {node_name}: {state_summary}")
    
    def trace_decision(self, decision_type: str, reason: str):
        """记录决策"""
        self._logger.info(f"DECISION {decision_type}: {reason}")
    
    def trace_skill_dispatch(self, skill_name: str, params: dict):
        """记录技能派发"""
        self._logger.info(f"DISPATCH {skill_name}: {params}")
    
    def trace_skill_result(self, skill_name: str, success: bool, message: str):
        """记录技能结果"""
        status = "SUCCESS" if success else "FAILED"
        self._logger.info(f"RESULT {skill_name} {status}: {message}")
    
    def trace_mode_change(self, old_mode: str, new_mode: str, reason: str):
        """记录模式变化"""
        self._logger.info(f"MODE {old_mode} -> {new_mode}: {reason}")
    
    def trace_checkpoint(self, checkpoint_id: str, node_name: str):
        """记录检查点"""
        self._logger.debug(f"CHECKPOINT {checkpoint_id} at {node_name}")
    
    def trace_error(self, error_type: str, message: str):
        """记录错误"""
        self._logger.error(f"ERROR {error_type}: {message}")
