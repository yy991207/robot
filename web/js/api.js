/**
 * API 调用模块
 */
const API = {
    baseUrl: '',

    async get(path) {
        const res = await fetch(this.baseUrl + path);
        return res.json();
    },

    async post(path, data) {
        const res = await fetch(this.baseUrl + path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return res.json();
    },

    // 获取状态
    async getStatus() {
        return this.get('/api/status');
    },

    // 获取地图
    async getMap() {
        return this.get('/api/map');
    },

    // 发送对话
    async chat(message, threadId = 'default') {
        return this.post('/api/chat', { message, thread_id: threadId });
    },

    // 执行命令
    async command(cmd, threadId = 'default') {
        return this.post('/api/command', { command: cmd, thread_id: threadId });
    },

    // 添加障碍物
    async addObstacle(x, y, width = 1, height = 1) {
        return this.post('/api/map/obstacle', {
            action: 'add',
            obstacle: { x, y, width, height }
        });
    },

    // 移除障碍物
    async removeObstacle(id) {
        return this.post('/api/map/obstacle', {
            action: 'remove',
            obstacle: { id }
        });
    },

    // 移动障碍物
    async moveObstacle(id, x, y) {
        return this.post('/api/map/obstacle', {
            action: 'move',
            obstacle: { id, x, y }
        });
    },

    // 停止
    async stop() {
        return this.post('/api/robot/stop', {});
    },

    // 暂停
    async pause() {
        return this.post('/api/robot/pause', {});
    },

    // 继续
    async resume() {
        return this.post('/api/robot/resume', {});
    }
};
