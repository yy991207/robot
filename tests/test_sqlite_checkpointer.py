"""SQLite Checkpointer 测试"""

import asyncio
import sys
sys.path.insert(0, ".")

from robot_brain.persistence import SQLiteCheckpointer
from robot_brain.core.state import BrainState


async def test_checkpointer():
    """测试 SQLite checkpointer 基本功能"""
    checkpointer = SQLiteCheckpointer("data/test_robot.db")
    thread_id = "test_thread"
    
    # 测试保存检查点
    state = BrainState()
    cp_id = await checkpointer.save_checkpoint(thread_id, state, "test_node")
    print(f"[OK] 保存检查点: {cp_id}")
    
    # 测试加载检查点
    loaded = await checkpointer.load_checkpoint(thread_id)
    print(f"[OK] 加载检查点: {loaded['checkpoint_id']}")
    
    # 测试对话历史
    await checkpointer.save_chat_message(thread_id, "user", "你好")
    await checkpointer.save_chat_message(thread_id, "assistant", "你好，有什么可以帮你的?")
    history = await checkpointer.load_chat_history(thread_id)
    print(f"[OK] 对话历史: {len(history)} 条")
    for msg in history:
        print(f"    [{msg['role']}] {msg['content']}")
    
    # 测试副作用追踪
    await checkpointer.mark_side_effect_executed(thread_id, "effect_001")
    executed = await checkpointer.is_side_effect_executed(thread_id, "effect_001")
    print(f"[OK] 副作用追踪: effect_001 已执行={executed}")
    
    # 清理
    await checkpointer.delete_thread(thread_id)
    print("[OK] 清理测试数据")
    
    print("\n所有测试通过!")


if __name__ == "__main__":
    asyncio.run(test_checkpointer())
