"""
Checkpointer

持久化组件，支持 durable execution
"""

import json
import os
import time
from typing import Dict, Any, Optional, List
from pathlib import Path

from robot_brain.core.state import BrainState


class Checkpoint:
    """检查点数据"""
    
    def __init__(
        self,
        thread_id: str,
        checkpoint_id: str,
        state: BrainState,
        timestamp: float,
        node_name: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.thread_id = thread_id
        self.checkpoint_id = checkpoint_id
        self.state = state
        self.timestamp = timestamp
        self.node_name = node_name
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "checkpoint_id": self.checkpoint_id,
            "state": json.loads(self.state.serialize()),
            "timestamp": self.timestamp,
            "node_name": self.node_name,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        return cls(
            thread_id=data["thread_id"],
            checkpoint_id=data["checkpoint_id"],
            state=BrainState._from_dict(data["state"]),
            timestamp=data["timestamp"],
            node_name=data.get("node_name", ""),
            metadata=data.get("metadata", {})
        )


class MemoryCheckpointer:
    """内存检查点存储"""
    
    def __init__(self):
        self._checkpoints: Dict[str, List[Checkpoint]] = {}
        self._executed_side_effects: Dict[str, set] = {}
    
    def save(
        self,
        thread_id: str,
        state: BrainState,
        node_name: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """保存检查点"""
        checkpoint_id = f"cp_{int(time.time() * 1000)}"
        
        checkpoint = Checkpoint(
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            state=state,
            timestamp=time.time(),
            node_name=node_name,
            metadata=metadata
        )
        
        if thread_id not in self._checkpoints:
            self._checkpoints[thread_id] = []
        
        self._checkpoints[thread_id].append(checkpoint)
        
        return checkpoint_id
    
    def load(self, thread_id: str, checkpoint_id: Optional[str] = None) -> Optional[Checkpoint]:
        """加载检查点"""
        if thread_id not in self._checkpoints:
            return None
        
        checkpoints = self._checkpoints[thread_id]
        if not checkpoints:
            return None
        
        if checkpoint_id:
            for cp in checkpoints:
                if cp.checkpoint_id == checkpoint_id:
                    return cp
            return None
        
        # 返回最新的检查点
        return checkpoints[-1]
    
    def list_checkpoints(self, thread_id: str) -> List[Checkpoint]:
        """列出线程的所有检查点"""
        return self._checkpoints.get(thread_id, [])
    
    def delete(self, thread_id: str, checkpoint_id: Optional[str] = None) -> bool:
        """删除检查点"""
        if thread_id not in self._checkpoints:
            return False
        
        if checkpoint_id:
            self._checkpoints[thread_id] = [
                cp for cp in self._checkpoints[thread_id]
                if cp.checkpoint_id != checkpoint_id
            ]
        else:
            del self._checkpoints[thread_id]
        
        return True
    
    def mark_side_effect_executed(self, thread_id: str, effect_id: str):
        """标记副作用已执行"""
        if thread_id not in self._executed_side_effects:
            self._executed_side_effects[thread_id] = set()
        self._executed_side_effects[thread_id].add(effect_id)
    
    def is_side_effect_executed(self, thread_id: str, effect_id: str) -> bool:
        """检查副作用是否已执行"""
        return effect_id in self._executed_side_effects.get(thread_id, set())


class FileCheckpointer:
    """文件检查点存储"""
    
    def __init__(self, storage_dir: str = ".checkpoints"):
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._side_effects_file = self._storage_dir / "side_effects.json"
        self._side_effects: Dict[str, List[str]] = self._load_side_effects()
    
    def _get_thread_dir(self, thread_id: str) -> Path:
        thread_dir = self._storage_dir / thread_id
        thread_dir.mkdir(parents=True, exist_ok=True)
        return thread_dir
    
    def _load_side_effects(self) -> Dict[str, List[str]]:
        if self._side_effects_file.exists():
            with open(self._side_effects_file, "r") as f:
                return json.load(f)
        return {}
    
    def _save_side_effects(self):
        with open(self._side_effects_file, "w") as f:
            json.dump(self._side_effects, f)
    
    def save(
        self,
        thread_id: str,
        state: BrainState,
        node_name: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """保存检查点到文件"""
        checkpoint_id = f"cp_{int(time.time() * 1000)}"
        
        checkpoint = Checkpoint(
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            state=state,
            timestamp=time.time(),
            node_name=node_name,
            metadata=metadata
        )
        
        thread_dir = self._get_thread_dir(thread_id)
        checkpoint_file = thread_dir / f"{checkpoint_id}.json"
        
        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint.to_dict(), f, ensure_ascii=False, indent=2)
        
        return checkpoint_id
    
    def load(self, thread_id: str, checkpoint_id: Optional[str] = None) -> Optional[Checkpoint]:
        """从文件加载检查点"""
        thread_dir = self._get_thread_dir(thread_id)
        
        if checkpoint_id:
            checkpoint_file = thread_dir / f"{checkpoint_id}.json"
            if checkpoint_file.exists():
                with open(checkpoint_file, "r") as f:
                    return Checkpoint.from_dict(json.load(f))
            return None
        
        # 返回最新的检查点
        checkpoint_files = sorted(thread_dir.glob("cp_*.json"), reverse=True)
        if checkpoint_files:
            with open(checkpoint_files[0], "r") as f:
                return Checkpoint.from_dict(json.load(f))
        
        return None
    
    def list_checkpoints(self, thread_id: str) -> List[Checkpoint]:
        """列出线程的所有检查点"""
        thread_dir = self._get_thread_dir(thread_id)
        checkpoints = []
        
        for checkpoint_file in sorted(thread_dir.glob("cp_*.json")):
            with open(checkpoint_file, "r") as f:
                checkpoints.append(Checkpoint.from_dict(json.load(f)))
        
        return checkpoints
    
    def delete(self, thread_id: str, checkpoint_id: Optional[str] = None) -> bool:
        """删除检查点文件"""
        thread_dir = self._get_thread_dir(thread_id)
        
        if checkpoint_id:
            checkpoint_file = thread_dir / f"{checkpoint_id}.json"
            if checkpoint_file.exists():
                checkpoint_file.unlink()
                return True
            return False
        
        # 删除整个线程目录
        import shutil
        if thread_dir.exists():
            shutil.rmtree(thread_dir)
            return True
        return False
    
    def mark_side_effect_executed(self, thread_id: str, effect_id: str):
        """标记副作用已执行"""
        if thread_id not in self._side_effects:
            self._side_effects[thread_id] = []
        if effect_id not in self._side_effects[thread_id]:
            self._side_effects[thread_id].append(effect_id)
            self._save_side_effects()
    
    def is_side_effect_executed(self, thread_id: str, effect_id: str) -> bool:
        """检查副作用是否已执行"""
        return effect_id in self._side_effects.get(thread_id, [])
