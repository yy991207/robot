"""
SQLite Checkpointer

使用 LangGraph 的 SQLite checkpoint 实现状态和对话持久化
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

import aiosqlite

from robot_brain.core.state import BrainState


class SQLiteCheckpointer:
    """
    SQLite 检查点存储
    
    功能：
    - 状态持久化（BrainState）
    - 对话历史存储
    - 副作用追踪
    - 支持多线程/会话
    """
    
    def __init__(self, db_path: str = "data/robot_brain.db"):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False
    
    async def _ensure_initialized(self):
        """确保数据库表已创建"""
        if self._initialized:
            return
        
        async with aiosqlite.connect(self._db_path) as db:
            # 检查点表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL UNIQUE,
                    state_json TEXT NOT NULL,
                    node_name TEXT,
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 对话历史表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 副作用追踪表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS side_effects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    effect_id TEXT NOT NULL,
                    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(thread_id, effect_id)
                )
            """)
            
            # 索引
            await db.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_thread ON checkpoints(thread_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_chat_thread ON chat_history(thread_id)")
            
            await db.commit()
        
        self._initialized = True
    
    async def save_checkpoint(
        self,
        thread_id: str,
        state: BrainState,
        node_name: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """保存检查点"""
        await self._ensure_initialized()
        
        checkpoint_id = f"cp_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """INSERT INTO checkpoints (thread_id, checkpoint_id, state_json, node_name, metadata_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    thread_id,
                    checkpoint_id,
                    state.serialize(),
                    node_name,
                    json.dumps(metadata or {}, ensure_ascii=False)
                )
            )
            await db.commit()
        
        return checkpoint_id
    
    async def load_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """加载检查点"""
        await self._ensure_initialized()
        
        async with aiosqlite.connect(self._db_path) as db:
            if checkpoint_id:
                cursor = await db.execute(
                    "SELECT * FROM checkpoints WHERE checkpoint_id = ?",
                    (checkpoint_id,)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM checkpoints WHERE thread_id = ? ORDER BY created_at DESC LIMIT 1",
                    (thread_id,)
                )
            
            row = await cursor.fetchone()
            if not row:
                return None
            
            return {
                "thread_id": row[1],
                "checkpoint_id": row[2],
                "state": BrainState._from_dict(json.loads(row[3])),
                "node_name": row[4],
                "metadata": json.loads(row[5]) if row[5] else {},
                "created_at": row[6]
            }
    
    async def list_checkpoints(self, thread_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """列出检查点"""
        await self._ensure_initialized()
        
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT checkpoint_id, node_name, created_at FROM checkpoints WHERE thread_id = ? ORDER BY created_at DESC LIMIT ?",
                (thread_id, limit)
            )
            rows = await cursor.fetchall()
            
            return [
                {"checkpoint_id": row[0], "node_name": row[1], "created_at": row[2]}
                for row in rows
            ]
    
    async def save_chat_message(self, thread_id: str, role: str, content: str):
        """保存对话消息"""
        await self._ensure_initialized()
        
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO chat_history (thread_id, role, content) VALUES (?, ?, ?)",
                (thread_id, role, content)
            )
            await db.commit()
    
    async def load_chat_history(self, thread_id: str, limit: int = 20) -> List[Dict[str, str]]:
        """加载对话历史"""
        await self._ensure_initialized()
        
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT role, content FROM chat_history WHERE thread_id = ? ORDER BY id DESC LIMIT ?",
                (thread_id, limit)
            )
            rows = await cursor.fetchall()
            
            # 反转顺序，最早的在前
            return [{"role": row[0], "content": row[1]} for row in reversed(rows)]
    
    async def clear_chat_history(self, thread_id: str):
        """清空对话历史"""
        await self._ensure_initialized()
        
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("DELETE FROM chat_history WHERE thread_id = ?", (thread_id,))
            await db.commit()
    
    async def mark_side_effect_executed(self, thread_id: str, effect_id: str):
        """标记副作用已执行"""
        await self._ensure_initialized()
        
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO side_effects (thread_id, effect_id) VALUES (?, ?)",
                (thread_id, effect_id)
            )
            await db.commit()
    
    async def is_side_effect_executed(self, thread_id: str, effect_id: str) -> bool:
        """检查副作用是否已执行"""
        await self._ensure_initialized()
        
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM side_effects WHERE thread_id = ? AND effect_id = ?",
                (thread_id, effect_id)
            )
            return await cursor.fetchone() is not None
    
    async def list_threads(self) -> List[str]:
        """列出所有线程"""
        await self._ensure_initialized()
        
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT DISTINCT thread_id FROM checkpoints ORDER BY thread_id"
            )
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
    
    async def delete_thread(self, thread_id: str):
        """删除线程的所有数据"""
        await self._ensure_initialized()
        
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
            await db.execute("DELETE FROM chat_history WHERE thread_id = ?", (thread_id,))
            await db.execute("DELETE FROM side_effects WHERE thread_id = ?", (thread_id,))
            await db.commit()
