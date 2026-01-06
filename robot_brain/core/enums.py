"""核心枚举类型定义"""

from enum import Enum


class Mode(Enum):
    """系统运行模式"""
    SAFE = "SAFE"       # 安全覆盖模式
    CHARGE = "CHARGE"   # 充电模式
    EXEC = "EXEC"       # 正常执行模式
    IDLE = "IDLE"       # 空闲等待模式


class DecisionType(Enum):
    """LLM 决策类型"""
    CONTINUE = "CONTINUE"         # 继续当前计划
    REPLAN = "REPLAN"             # 重新规划
    RETRY = "RETRY"               # 重试当前操作
    SWITCH_TASK = "SWITCH_TASK"   # 切换任务
    ASK_HUMAN = "ASK_HUMAN"       # 请求人工干预
    FINISH = "FINISH"             # 任务完成
    ABORT = "ABORT"               # 中止任务


class UserInterruptType(Enum):
    """用户中断类型"""
    NONE = "NONE"           # 无中断
    PAUSE = "PAUSE"         # 暂停
    STOP = "STOP"           # 停止
    NEW_GOAL = "NEW_GOAL"   # 新目标


class ApprovalAction(Enum):
    """审批动作类型"""
    APPROVE = "APPROVE"   # 批准
    EDIT = "EDIT"         # 编辑后批准
    REJECT = "REJECT"     # 拒绝


class SkillStatus(Enum):
    """技能执行状态"""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RUNNING = "RUNNING"
    PENDING = "PENDING"


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class InterfaceType(Enum):
    """技能接口类型"""
    ROS2_ACTION = "ros2_action"
    ROS2_SERVICE = "ros2_service"
    INTERNAL = "internal"
