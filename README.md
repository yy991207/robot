# Robot Brain

基于 LangGraph 的机器人大脑调度系统，采用双环架构实现智能任务调度和执行。

## 特性

- 双环调度架构：Kernel 外环 + ReAct 内环
- 状态持久化：支持检查点恢复
- 人机交互：HITL 审批机制
- 技能管理：可扩展的技能注册表
- 属性测试：64 个测试用例全部通过

## 架构

```
┌─────────────────────────────────────────┐
│           Kernel 外环 (10Hz)             │
│  HCI入口 → 遥测同步 → 世界更新 → 事件仲裁  │
│     ↓                           ↓       │
│  任务队列 ←───────────────── 路由决策    │
└─────────────────────────────────────────┘
                    ↓ (EXEC 模式)
┌─────────────────────────────────────────┐
│              ReAct 内环                  │
│  构建观测 → LLM决策 → 编译操作 → 护栏检查  │
│     ↑                           ↓       │
│  停止判断 ← 观察结果 ← 派发技能 ← 人类审批 │
└─────────────────────────────────────────┘
```

## 安装

```bash
# 创建 conda 环境
conda create -n robot python=3.10
conda activate robot

# 安装依赖
pip install -e .
```

## 运行测试

```bash
pytest tests/ -v
```

## 项目结构

```
robot_brain/
├── core/           # 核心数据模型
├── service/
│   ├── kernel/     # Kernel 外环服务
│   ├── react/      # ReAct 内环服务
│   └── skill/      # 技能服务
├── graph/          # LangGraph 图定义
├── persistence/    # 持久化层
├── main.py         # 主入口
└── logging_config.py
```

## 运行模式

| 模式 | 说明 |
|------|------|
| IDLE | 空闲模式 |
| EXEC | 执行模式 |
| SAFE | 安全模式 |
| CHARGE | 充电模式 |

## 文档

- [架构文档](doc/architecture.md)
- [测试报告](doc/test_report.md)

## License

MIT
