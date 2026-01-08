/**
 * 应用主入口
 */
class App {
    constructor() {
        this.map = new MapRenderer('map-canvas');
        this.robot = new RobotAnimator(this.map);
        this.chat = new ChatManager();
        this.ws = new RobotWebSocket('web_client');
        
        this.setupUI();
        this.setupWebSocket();
        this.init();
    }

    async init() {
        // 加载地图
        try {
            const mapData = await API.getMap();
            this.map.setZones(mapData.zones);
            this.map.setObstacles(mapData.obstacles);
            this.map.render();
        } catch (e) {
            console.error('Load map failed:', e);
        }
        
        // 加载状态
        try {
            const status = await API.getStatus();
            this.updateStatus(status);
        } catch (e) {
            console.error('Load status failed:', e);
        }
        
        // 连接 WebSocket
        this.ws.connect();
    }

    setupUI() {
        // 控制按钮
        document.getElementById('btn-stop').addEventListener('click', async () => {
            await API.stop();
            this.chat.addMessage('system', '已停止');
        });
        
        document.getElementById('btn-pause').addEventListener('click', async () => {
            await API.pause();
            this.chat.addMessage('system', '已暂停');
        });
        
        document.getElementById('btn-resume').addEventListener('click', async () => {
            await API.resume();
            this.chat.addMessage('system', '已继续');
        });
        
        // 障碍物按钮
        document.getElementById('btn-add-obstacle').addEventListener('click', () => {
            this.map.setAddingMode(true);
            this.chat.addMessage('system', '点击地图添加障碍物');
        });
        
        document.getElementById('btn-clear-obstacles').addEventListener('click', async () => {
            for (const obs of [...this.map.obstacles]) {
                await API.removeObstacle(obs.id);
            }
            this.map.setObstacles([]);
            this.chat.addMessage('system', '已清除所有障碍物');
        });
    }

    setupWebSocket() {
        this.ws.on('robot_position', (data) => {
            this.robot.setTarget(data.x, data.y, data.theta);
            document.getElementById('position').textContent = 
                `(${data.x.toFixed(1)}, ${data.y.toFixed(1)})`;
            document.getElementById('battery').textContent = 
                `${data.battery_pct.toFixed(0)}%`;
        });
        
        this.ws.on('init', (data) => {
            this.robot.setPosition(data.robot.x, data.robot.y, data.robot.theta);
            if (data.obstacles) {
                this.map.setObstacles(data.obstacles);
            }
        });
        
        this.ws.on('obstacles_update', (data) => {
            this.map.setObstacles(data.obstacles);
        });
        
        this.ws.on('task_update', (data) => {
            document.getElementById('task').textContent = data.goal || '无';
            document.getElementById('mode').textContent = data.mode || 'IDLE';
        });
        
        this.ws.on('speak', (data) => {
            this.chat.addMessage('assistant', data.message);
        });
        
        this.ws.on('path_update', (data) => {
            this.map.setPath(data.path);
        });
    }

    updateStatus(status) {
        if (status.robot) {
            this.robot.setPosition(
                status.robot.x, 
                status.robot.y, 
                status.robot.theta
            );
            document.getElementById('position').textContent = 
                `(${status.robot.x.toFixed(1)}, ${status.robot.y.toFixed(1)})`;
            document.getElementById('battery').textContent = 
                `${status.robot.battery_pct.toFixed(0)}%`;
        }
        
        if (status.task) {
            document.getElementById('task').textContent = status.task.goal || '无';
            document.getElementById('mode').textContent = status.task.mode;
        }
    }

    async addObstacle(x, y) {
        try {
            const res = await API.addObstacle(x, y);
            if (res.success) {
                this.map.setObstacles(res.obstacles);
                this.chat.addMessage('system', `障碍物已添加 (${x}, ${y})`);
                
                if (res.robot_reaction?.detected) {
                    this.chat.addMessage('system', 
                        `机器人检测到障碍物，${res.robot_reaction.action}`);
                }
            }
        } catch (e) {
            console.error('Add obstacle failed:', e);
        }
    }

    async moveObstacle(id, x, y) {
        try {
            const res = await API.moveObstacle(id, x, y);
            if (res.success) {
                this.map.setObstacles(res.obstacles);
            }
        } catch (e) {
            console.error('Move obstacle failed:', e);
        }
    }
}

// 启动应用
window.app = new App();
