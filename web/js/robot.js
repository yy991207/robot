/**
 * 机器人动画模块
 */
class RobotAnimator {
    constructor(mapRenderer) {
        this.map = mapRenderer;
        this.targetX = 0;
        this.targetY = 0;
        this.targetTheta = 0;
        this.currentX = 0;
        this.currentY = 0;
        this.currentTheta = 0;
        this.animating = false;
    }

    setTarget(x, y, theta) {
        this.targetX = x;
        this.targetY = y;
        this.targetTheta = theta;
        
        if (!this.animating) {
            this.animate();
        }
    }

    animate() {
        this.animating = true;
        
        const lerp = (a, b, t) => a + (b - a) * t;
        const speed = 0.15;
        
        this.currentX = lerp(this.currentX, this.targetX, speed);
        this.currentY = lerp(this.currentY, this.targetY, speed);
        this.currentTheta = lerp(this.currentTheta, this.targetTheta, speed);
        
        this.map.updateRobot(this.currentX, this.currentY, this.currentTheta);
        
        const dx = Math.abs(this.currentX - this.targetX);
        const dy = Math.abs(this.currentY - this.targetY);
        
        if (dx > 0.01 || dy > 0.01) {
            requestAnimationFrame(() => this.animate());
        } else {
            this.animating = false;
        }
    }

    setPosition(x, y, theta) {
        this.currentX = x;
        this.currentY = y;
        this.currentTheta = theta;
        this.targetX = x;
        this.targetY = y;
        this.targetTheta = theta;
        this.map.updateRobot(x, y, theta);
    }
}
