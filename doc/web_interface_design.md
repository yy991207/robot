# Robot Brain Web 可视化交互系统设计文档

## 1. 系统概述

基于现有 Robot Brain 后端，构建 Web 可视化交互系统，实现：
- 机器人移动动画展示
- 文字交互（命令/闲聊自动识别）
- 动态障碍物拖拽
- 实时状态监控

## 2. 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + WebSocket |
| 前端 | 原生 HTML/CSS/JS + Canvas |
| 通信 | REST API + WebSocket |
| 动画 | Canvas 2D |

## 3. 目录结构

```
D:\robot\
├── robot_brain/
│   └── api/                    # 新增 API 层
│       ├── __init__.py
│       ├── server.py           # FastAPI 主入口
│       ├── routes/
│       │   ├── __init__.py
│       │   ├── chat.py         # 对话接口
│       │   ├── command.py      # 命令接口
│       │   ├── map.py          # 地图/障碍物接口
│       │   └── status.py       # 状态接口
│       └── websocket.py        # WebSocket 处理
├── web/                        # 前端目录
│   ├── index.html
│   ├── css/
│   │   ├── main.css
│   │   ├── map.css
│   │   └── chat.css
│   ├── js/
│   │   ├── app.js              # 主入口
│   │   ├── api.js              # API 调用
│   │   ├── websocket.js        # WebSocket 客户端
│   │   ├── map.js              # 地图渲染
│   │   ├── robot.js            # 机器人动画
│   │   └── chat.js             # 对话组件
│   └── assets/
│       └── sprites/            # 开源素材
│           ├── robot.png
│           └── obstacle.png
└── doc/
    └── web_interface_design.md
```

## 4. API 接口设计

### 4.1 对话接口

```
POST /api/chat
```

**请求体：**
```json
{
  "message": "你好",
  "thread_id": "session_001"
}
```

**响应：**
```json
{
  "type": "chat",           // chat | command
  "response": "你好，有什么可以帮你的？",
  "intent": null            // 如果是命令则返回解析结果
}
```

**流式对话（SSE）：**
```
GET /api/chat/stream?message=xxx&thread_id=xxx
```

### 4.2 命令接口

```
POST /api/command
```

**请求体：**
```json
{
  "command": "go to kitchen",
  "thread_id": "session_001"
}
```

**响应：**
```json
{
  "success": true,
  "task_id": "task_xxx",
  "message": "已创建导航任务"
}
```

### 4.3 状态接口

```
GET /api/status
```

**响应：**
```json
{
  "robot": {
    "x": 2.5,
    "y": 3.0,
    "theta": 1.57,
    "battery_pct": 85.0,
    "state": "moving"
  },
  "task": {
    "active_task_id": "task_xxx",
    "goal": "navigate_to:kitchen",
    "mode": "EXEC"
  },
  "skills": {
    "running": ["NavigateToPose"]
  }
}
```

### 4.4 地图接口

```
GET /api/map
```

**响应：**
```json
{
  "width": 16,
  "height": 16,
  "zones": [
    {"name": "kitchen", "x": 2, "y": 2, "radius": 1},
    {"name": "living_room", "x": 10, "y": 5, "radius": 1},
    {"name": "bedroom", "x": 2, "y": 7, "radius": 1},
    {"name": "bathroom", "x": 7, "y": 12, "radius": 1},
    {"name": "charging_station", "x": -1, "y": 1, "radius": 0.5}
  ],
  "obstacles": [
    {"id": "obs_001", "x": 5, "y": 5, "width": 1, "height": 1}
  ]
}
```

### 4.5 障碍物操作接口

```
POST /api/map/obstacle
```

**请求体：**
```json
{
  "action": "add",          // add | remove | move
  "obstacle": {
    "id": "obs_002",
    "x": 6,
    "y": 8,
    "width": 1,
    "height": 1
  }
}
```

**响应：**
```json
{
  "success": true,
  "obstacles": [...],       // 更新后的障碍物列表
  "robot_reaction": {
    "detected": true,
    "action": "replanning", // replanning | stopped | none
    "new_path": [[2,2], [3,3], [4,5], ...]
  }
}
```

### 4.6 WebSocket 实时推送

```
WS /ws/{thread_id}
```

**服务端推送消息类型：**

```json
// 机器人位置更新（10Hz）
{
  "type": "robot_position",
  "data": {"x": 2.5, "y": 3.0, "theta": 1.57}
}

// 任务状态变化
{
  "type": "task_update",
  "data": {"task_id": "xxx", "status": "completed"}
}

// 决策事件
{
  "type": "decision",
  "data": {"type": "CONTINUE", "reason": "..."}
}

// 机器人说话
{
  "type": "speak",
  "data": {"message": "已到达厨房"}
}

// 路径更新
{
  "type": "path_update",
  "data": {"path": [[0,0], [1,1], [2,2]]}
}
```

## 5. 前端页面设计

### 5.1 布局

```
+--------------------------------------------------+
|                    顶部状态栏                      |
|  电量: 85%  |  模式: EXEC  |  任务: 导航到厨房      |
+--------------------------------------------------+
|                                    |              |
|                                    |   对话区域    |
|           地图可视化区域             |              |
|         (Canvas 渲染)              |  [消息列表]   |
|                                    |              |
|    [机器人] -----> [目标]           |  [输入框]    |
|                                    |              |
+--------------------------------------------------+
|                    底部控制栏                      |
|  [停止] [暂停] [继续]  |  障碍物: [拖拽添加]        |
+--------------------------------------------------+
```

### 5.2 配色方案（简洁风格）

```css
:root {
  --bg-primary: #f5f5f5;      /* 浅灰背景 */
  --bg-secondary: #ffffff;     /* 白色卡片 */
  --text-primary: #333333;     /* 深灰文字 */
  --text-secondary: #666666;   /* 次要文字 */
  --accent: #2196F3;           /* 蓝色强调 */
  --success: #4CAF50;          /* 绿色成功 */
  --warning: #FF9800;          /* 橙色警告 */
  --danger: #F44336;           /* 红色危险 */
  --border: #e0e0e0;           /* 边框色 */
}
```

### 5.3 地图渲染

- 使用 Canvas 2D 绘制
- 网格背景（16x16）
- 区域用不同颜色圆形标记
- 机器人用图标 + 方向箭头
- 障碍物用灰色方块
- 路径用虚线显示
- 支持拖拽添加障碍物

### 5.4 机器人动画

- 平滑移动插值（lerp）
- 旋转动画
- 移动时显示轨迹
- 到达目标时闪烁提示

## 6. 开源素材

推荐使用以下开源素材：

1. **机器人图标**: [OpenGameArt - Robot](https://opengameart.org/content/robot-sprite)
2. **地图元素**: [Kenney Assets](https://kenney.nl/assets) - 免费游戏素材
3. **图标**: [Feather Icons](https://feathericons.com/) - MIT 协议

或使用简单几何图形：
- 机器人: 圆形 + 方向三角
- 障碍物: 灰色矩形
- 区域: 彩色圆形 + 标签

## 7. 执行步骤

### 7.1 安装依赖

```bash
# WSL 中执行
source ~/miniconda/etc/profile.d/conda.sh
conda activate robot
pip install fastapi uvicorn python-multipart -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 7.2 启动服务

```bash
# WSL 中执行
source ~/miniconda/etc/profile.d/conda.sh
conda activate robot
cd /mnt/d/robot
python -m uvicorn robot_brain.api.server:app --host 0.0.0.0 --port 8000 --reload
```

### 7.3 访问前端

浏览器打开: http://localhost:8000

### 7.4 功能测试

1. 对话测试: 输入 "你好" 测试闲聊
2. 命令测试: 输入 "去厨房" 测试导航
3. 障碍物测试: 点击"添加障碍物"按钮，然后点击地图
4. 拖拽测试: 拖动障碍物到新位置

## 8. 接口汇总

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/chat | 对话（自动识别命令/闲聊） |
| GET | /api/chat/stream | 流式对话 |
| POST | /api/command | 执行命令 |
| GET | /api/status | 获取状态 |
| GET | /api/map | 获取地图 |
| POST | /api/map/obstacle | 操作障碍物 |
| POST | /api/robot/stop | 紧急停止 |
| POST | /api/robot/pause | 暂停 |
| POST | /api/robot/resume | 继续 |
| WS | /ws/{thread_id} | 实时推送 |

## 9. 核心交互流程

### 9.1 文字输入流程

```
用户输入 -> POST /api/chat -> 后端解析意图
    |
    +-> 闲聊 -> LLM 生成回复 -> 返回对话
    |
    +-> 命令 -> 创建任务 -> 返回任务ID -> WebSocket 推送执行状态
```

### 9.2 障碍物拖拽流程

```
用户拖拽 -> POST /api/map/obstacle -> 更新地图
    |
    +-> 检测机器人路径冲突
    |
    +-> 触发重规划 -> WebSocket 推送新路径
    |
    +-> 前端动画更新
```

### 9.3 实时位置更新流程

```
后端模拟器 (10Hz) -> 计算新位置 -> WebSocket 推送
    |
    +-> 前端接收 -> Canvas 重绘 -> 平滑动画
```

## 10. 下一步

1. 创建 `robot_brain/api/` 后端模块
2. 创建 `web/` 前端文件
3. 集成测试
4. 优化动画效果
