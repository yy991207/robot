"""WebSocket 处理"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json


router = APIRouter()


@router.websocket("/ws/{thread_id}")
async def websocket_endpoint(websocket: WebSocket, thread_id: str):
    """WebSocket 连接"""
    await websocket.accept()
    
    app_state = websocket.app.state.app_state
    app_state.add_ws_connection(thread_id, websocket)
    
    try:
        # 发送初始状态
        if app_state.brain and app_state.brain.state:
            state = app_state.brain.state
            theta = app_state._quaternion_to_yaw(state.robot.pose)
            await websocket.send_json({
                "type": "init",
                "data": {
                    "robot": {
                        "x": state.robot.pose.x,
                        "y": state.robot.pose.y,
                        "theta": theta
                    },
                    "obstacles": app_state.obstacles
                }
            })
        
        # 保持连接
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            # 处理客户端消息
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        app_state.remove_ws_connection(thread_id, websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        app_state.remove_ws_connection(thread_id, websocket)
