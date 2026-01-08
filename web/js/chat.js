/**
 * 对话模块
 */
class ChatManager {
    constructor() {
        this.container = document.getElementById('chat-messages');
        this.input = document.getElementById('chat-input');
        this.sendBtn = document.getElementById('btn-send');
        
        this.setupEvents();
    }

    setupEvents() {
        this.sendBtn.addEventListener('click', () => this.send());
        this.input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.send();
        });
    }

    async send() {
        const text = this.input.value.trim();
        if (!text) return;
        
        this.input.value = '';
        this.addMessage('user', text);
        
        try {
            const res = await API.chat(text);
            
            if (res.type === 'command') {
                this.addMessage('system', `[命令] ${res.intent?.type || '已执行'}`);
            }
            
            if (res.response) {
                this.addMessage('assistant', res.response);
            }
        } catch (e) {
            this.addMessage('system', '发送失败: ' + e.message);
        }
    }

    addMessage(role, content) {
        const div = document.createElement('div');
        div.className = `message ${role}`;
        div.textContent = content;
        this.container.appendChild(div);
        this.container.scrollTop = this.container.scrollHeight;
    }
}
