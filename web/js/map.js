/**
 * 地图渲染模块
 */
class MapRenderer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.width = this.canvas.width;
        this.height = this.canvas.height;
        
        // 地图配置
        this.mapWidth = 16;
        this.mapHeight = 16;
        this.cellSize = this.width / this.mapWidth;
        this.offsetX = 2;  // 地图偏移（支持负坐标）
        
        // 数据
        this.zones = [];
        this.obstacles = [];
        this.robot = { x: 0, y: 0, theta: 0 };
        this.path = [];
        
        // 交互
        this.addingObstacle = false;
        this.draggingObstacle = null;
        
        this.setupEvents();
    }

    setupEvents() {
        this.canvas.addEventListener('click', (e) => this.onClick(e));
        this.canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.canvas.addEventListener('mouseup', (e) => this.onMouseUp(e));
    }

    // 屏幕坐标转地图坐标
    screenToMap(sx, sy) {
        const rect = this.canvas.getBoundingClientRect();
        const x = (sx - rect.left) / this.cellSize - this.offsetX;
        const y = this.mapHeight - (sy - rect.top) / this.cellSize;
        return { x: Math.round(x), y: Math.round(y) };
    }

    // 地图坐标转屏幕坐标
    mapToScreen(mx, my) {
        const sx = (mx + this.offsetX) * this.cellSize;
        const sy = (this.mapHeight - my) * this.cellSize;
        return { x: sx, y: sy };
    }

    onClick(e) {
        if (this.addingObstacle) {
            const pos = this.screenToMap(e.clientX, e.clientY);
            if (window.app) {
                window.app.addObstacle(pos.x, pos.y);
            }
            this.addingObstacle = false;
            this.canvas.style.cursor = 'crosshair';
        }
    }

    onMouseDown(e) {
        const pos = this.screenToMap(e.clientX, e.clientY);
        // 检查是否点击了障碍物
        for (const obs of this.obstacles) {
            if (Math.abs(pos.x - obs.x) < 1 && Math.abs(pos.y - obs.y) < 1) {
                this.draggingObstacle = obs;
                this.canvas.style.cursor = 'grabbing';
                break;
            }
        }
    }

    onMouseMove(e) {
        if (this.draggingObstacle) {
            const pos = this.screenToMap(e.clientX, e.clientY);
            this.draggingObstacle.x = pos.x;
            this.draggingObstacle.y = pos.y;
            this.render();
        }
    }

    onMouseUp(e) {
        if (this.draggingObstacle) {
            const obs = this.draggingObstacle;
            if (window.app) {
                window.app.moveObstacle(obs.id, obs.x, obs.y);
            }
            this.draggingObstacle = null;
            this.canvas.style.cursor = 'crosshair';
        }
    }

    setAddingMode(adding) {
        this.addingObstacle = adding;
        this.canvas.style.cursor = adding ? 'cell' : 'crosshair';
    }

    render() {
        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.width, this.height);
        
        this.drawGrid();
        this.drawZones();
        this.drawObstacles();
        this.drawPath();
        this.drawRobot();
    }

    drawGrid() {
        const ctx = this.ctx;
        ctx.strokeStyle = '#e0e0e0';
        ctx.lineWidth = 1;
        
        for (let i = 0; i <= this.mapWidth; i++) {
            ctx.beginPath();
            ctx.moveTo(i * this.cellSize, 0);
            ctx.lineTo(i * this.cellSize, this.height);
            ctx.stroke();
        }
        
        for (let i = 0; i <= this.mapHeight; i++) {
            ctx.beginPath();
            ctx.moveTo(0, i * this.cellSize);
            ctx.lineTo(this.width, i * this.cellSize);
            ctx.stroke();
        }
    }

    drawZones() {
        const ctx = this.ctx;
        
        for (const zone of this.zones) {
            const pos = this.mapToScreen(zone.x, zone.y);
            const radius = zone.radius * this.cellSize;
            
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
            ctx.fillStyle = zone.color + '40';
            ctx.fill();
            ctx.strokeStyle = zone.color;
            ctx.lineWidth = 2;
            ctx.stroke();
            
            // 标签
            ctx.fillStyle = zone.color;
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(zone.name, pos.x, pos.y + radius + 14);
        }
    }

    drawObstacles() {
        const ctx = this.ctx;
        
        for (const obs of this.obstacles) {
            const pos = this.mapToScreen(obs.x, obs.y);
            const w = (obs.width || 1) * this.cellSize;
            const h = (obs.height || 1) * this.cellSize;
            
            ctx.fillStyle = '#666666';
            ctx.fillRect(pos.x - w/2, pos.y - h/2, w, h);
            ctx.strokeStyle = '#333333';
            ctx.lineWidth = 2;
            ctx.strokeRect(pos.x - w/2, pos.y - h/2, w, h);
        }
    }

    drawPath() {
        if (this.path.length < 2) return;
        
        const ctx = this.ctx;
        ctx.strokeStyle = '#2196F3';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        
        ctx.beginPath();
        const start = this.mapToScreen(this.path[0][0], this.path[0][1]);
        ctx.moveTo(start.x, start.y);
        
        for (let i = 1; i < this.path.length; i++) {
            const p = this.mapToScreen(this.path[i][0], this.path[i][1]);
            ctx.lineTo(p.x, p.y);
        }
        ctx.stroke();
        ctx.setLineDash([]);
    }

    drawRobot() {
        const ctx = this.ctx;
        const pos = this.mapToScreen(this.robot.x, this.robot.y);
        const size = this.cellSize * 0.6;
        
        ctx.save();
        ctx.translate(pos.x, pos.y);
        ctx.rotate(-this.robot.theta);
        
        // 机器人身体
        ctx.beginPath();
        ctx.arc(0, 0, size/2, 0, Math.PI * 2);
        ctx.fillStyle = '#333333';
        ctx.fill();
        
        // 方向指示
        ctx.beginPath();
        ctx.moveTo(size/2, 0);
        ctx.lineTo(size/4, -size/4);
        ctx.lineTo(size/4, size/4);
        ctx.closePath();
        ctx.fillStyle = '#FF5722';
        ctx.fill();
        
        ctx.restore();
    }

    updateRobot(x, y, theta) {
        this.robot.x = x;
        this.robot.y = y;
        this.robot.theta = theta;
        this.render();
    }

    setZones(zones) {
        this.zones = zones;
    }

    setObstacles(obstacles) {
        this.obstacles = obstacles;
        this.render();
    }

    setPath(path) {
        this.path = path;
        this.render();
    }
}
