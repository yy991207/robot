"""对话接口"""

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from robot_brain.core.enums import UserInterruptType, Mode
from robot_brain.logging_config import get_logger


router = APIRouter()
logger = get_logger("api.chat")


class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    type: str  # chat | command
    response: str
    intent: Optional[dict] = None


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    """对话接口 - 简化版，LLM解析移到内环ReAct"""
    app_state = request.app.state.app_state
    logger.info(f"收到消息: {req.message}")
    
    # 直接注入用户输入，让Kernel和ReAct处理
    app_state.brain.inject_user_input(req.message)
    
    # 运行一次完整的brain循环
    await app_state.brain.run_once()
    
    state = app_state.brain.state
    logger.info(f"执行后: mode={state.tasks.mode.value}, active_task={state.tasks.active_task_id}")
    
    # 根据执行结果判断类型
    is_command = (
        state.tasks.mode != Mode.IDLE or
        state.hci.user_interrupt != UserInterruptType.NONE
    )
    
    # 获取回复
    response = ""
    if state.react.proposed_ops and state.react.proposed_ops.to_speak:
        response = " ".join(state.react.proposed_ops.to_speak)
    elif state.react.decision:
        response = state.react.decision.reason
    
    if is_command:
        logger.info(f"命令回复: {response}")
        return ChatResponse(
            type="command",
            response=response or "命令已接收",
            intent={
                "type": state.hci.user_interrupt.value,
                "payload": state.hci.interrupt_payload
            }
        )
    else:
        # 闲聊 - 使用ChatService
        logger.info("处理为闲聊")
        chat_response = await app_state.chat_service.chat(req.message)
        logger.info(f"闲聊回复: {chat_response[:50]}...")
        return ChatResponse(type="chat", response=chat_response)


@router.get("/chat/stream")
async def chat_stream(message: str, thread_id: str = "default", request: Request = None):
    """流式对话"""
    app_state = request.app.state.app_state
    
    async def generate():
        async for chunk in app_state.chat_service.chat_stream(message):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
