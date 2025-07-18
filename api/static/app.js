// ES Agent Demo Interface JavaScript

class ESAgentClient {
    constructor() {
        this.websocket = null;
        this.sessionId = null;
        this.queryCount = 0;
        this.currentQuery = null;
        this.isConnected = false;
        
        this.initializeElements();
        this.setupEventListeners();
        this.connect();
    }

    initializeElements() {
        this.elements = {
            chatMessages: document.getElementById('chat-messages'),
            queryInput: document.getElementById('query-input'),
            sendButton: document.getElementById('send-button'),
            cancelButton: document.getElementById('cancel-button'),
            connectionStatus: document.getElementById('connection-status'),
            sessionId: document.getElementById('session-id'),
            queryCount: document.getElementById('query-count'),
            progressContainer: document.getElementById('progress-container'),
            progressFill: document.getElementById('progress-fill'),
            progressText: document.getElementById('progress-text'),
            clearChatButton: document.getElementById('clear-chat'),
            downloadButton: document.getElementById('download-conversation'),
            reconnectButton: document.getElementById('reconnect')
        };
    }

    setupEventListeners() {
        // Send button and enter key
        this.elements.sendButton.addEventListener('click', () => this.sendQuery());
        this.elements.queryInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendQuery();
            }
        });

        // Cancel button
        this.elements.cancelButton.addEventListener('click', () => this.cancelQuery());

        // Example queries
        document.querySelectorAll('.example-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const query = e.target.getAttribute('data-query');
                this.elements.queryInput.value = query;
                this.sendQuery();
            });
        });

        // Action buttons
        this.elements.clearChatButton.addEventListener('click', () => this.clearChat());
        this.elements.downloadButton.addEventListener('click', () => this.downloadConversation());
        this.elements.reconnectButton.addEventListener('click', () => this.reconnect());
    }

    connect() {
        if (this.websocket) {
            this.websocket.close();
        }

        this.updateConnectionStatus('connecting');
        this.sessionId = this.generateSessionId();
        this.elements.sessionId.textContent = this.sessionId;

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/ws?session_id=${this.sessionId}`;

        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            this.isConnected = true;
            this.updateConnectionStatus('connected');
            this.addSystemMessage('Connected to ES Agent. Ready to process queries!');
        };

        this.websocket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleWebSocketMessage(message);
        };

        this.websocket.onclose = () => {
            this.isConnected = false;
            this.updateConnectionStatus('disconnected');
            this.addSystemMessage('Connection lost. Click "Reconnect" to restore connection.');
        };

        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.addErrorMessage('Connection error occurred. Please try reconnecting.');
        };
    }

    handleWebSocketMessage(message) {
        switch (message.type) {
            case 'progress':
                this.updateProgress(message);
                break;
            case 'result':
                this.handleQueryResult(message.data);
                break;
            case 'error':
                this.handleError(message);
                break;
            case 'pong':
                // Handle ping/pong for connection keepalive
                break;
            case 'cancelled':
                this.handleQueryCancelled();
                break;
            default:
                console.log('Unknown message type:', message.type);
        }
    }

    sendQuery() {
        const query = this.elements.queryInput.value.trim();
        if (!query || !this.isConnected) return;

        this.currentQuery = query;
        this.elements.queryInput.value = '';
        this.elements.sendButton.disabled = true;
        this.elements.cancelButton.style.display = 'inline-block';

        // Add user message to chat
        this.addUserMessage(query);

        // Show progress
        this.showProgress('Sending query...');

        // Send to WebSocket
        this.websocket.send(JSON.stringify({
            type: 'query',
            data: {
                query: query,
                session_id: this.sessionId
            }
        }));

        this.queryCount++;
        this.elements.queryCount.textContent = this.queryCount;
    }

    cancelQuery() {
        if (this.websocket && this.currentQuery) {
            this.websocket.send(JSON.stringify({
                type: 'cancel',
                data: { session_id: this.sessionId }
            }));
        }
    }

    updateProgress(message) {
        const progress = message.total_steps > 0 ? (message.step / message.total_steps) * 100 : 0;
        this.elements.progressFill.style.width = `${progress}%`;
        this.elements.progressText.textContent = message.message;
        
        if (message.details && message.details.tool) {
            this.elements.progressText.textContent += ` (${message.details.tool})`;
        }
    }

    handleQueryResult(data) {
        this.hideProgress();
        this.addAssistantMessage(data.response, data.sources, data.execution_plan);
        this.resetInputState();
    }

    handleError(message) {
        this.hideProgress();
        this.addErrorMessage(message.message);
        this.resetInputState();
    }

    handleQueryCancelled() {
        this.hideProgress();
        this.addSystemMessage('Query cancelled by user.');
        this.resetInputState();
    }

    addUserMessage(content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';
        messageDiv.innerHTML = `
            <div class="message-content">${this.escapeHtml(content)}</div>
            <div class="message-meta">${new Date().toLocaleTimeString()}</div>
        `;
        this.elements.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addAssistantMessage(content, sources = [], executionPlan = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant-message';
        
        let sourcesHtml = '';
        if (sources && sources.length > 0) {
            sourcesHtml = '<div class="message-sources"><strong>Sources:</strong>';
            sources.forEach(source => {
                sourcesHtml += `<div class="source-item">${source.title} (${source.type})</div>`;
            });
            sourcesHtml += '</div>';
        }

        messageDiv.innerHTML = `
            <div class="message-content">${this.escapeHtml(content)}</div>
            ${sourcesHtml}
            <div class="message-meta">${new Date().toLocaleTimeString()}</div>
        `;
        
        this.elements.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addSystemMessage(content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message system-message';
        messageDiv.innerHTML = `
            <div class="message-content">${this.escapeHtml(content)}</div>
            <div class="message-meta">${new Date().toLocaleTimeString()}</div>
        `;
        this.elements.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addErrorMessage(content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message error-message';
        messageDiv.innerHTML = `
            <div class="message-content"><strong>Error:</strong> ${this.escapeHtml(content)}</div>
            <div class="message-meta">${new Date().toLocaleTimeString()}</div>
        `;
        this.elements.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    showProgress(text) {
        this.elements.progressContainer.style.display = 'block';
        this.elements.progressText.textContent = text;
        this.elements.progressFill.style.width = '0%';
    }

    hideProgress() {
        this.elements.progressContainer.style.display = 'none';
    }

    resetInputState() {
        this.elements.sendButton.disabled = false;
        this.elements.cancelButton.style.display = 'none';
        this.currentQuery = null;
    }

    updateConnectionStatus(status) {
        this.elements.connectionStatus.className = `status-${status}`;
        this.elements.connectionStatus.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    }

    clearChat() {
        const systemMessages = this.elements.chatMessages.querySelectorAll('.system-message');
        this.elements.chatMessages.innerHTML = '';
        
        // Keep the welcome message
        if (systemMessages.length > 0) {
            this.elements.chatMessages.appendChild(systemMessages[0]);
        }
    }

    async downloadConversation() {
        if (!this.sessionId) return;

        try {
            const response = await fetch(`/api/debug/conversation/${this.sessionId}`);
            if (response.ok) {
                const data = await response.json();
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `es-agent-conversation-${this.sessionId}.json`;
                a.click();
                URL.revokeObjectURL(url);
            } else {
                this.addErrorMessage('Failed to download conversation data.');
            }
        } catch (error) {
            this.addErrorMessage('Error downloading conversation: ' + error.message);
        }
    }

    reconnect() {
        this.addSystemMessage('Reconnecting...');
        this.connect();
    }

    generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    scrollToBottom() {
        this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize the client when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new ESAgentClient();
});

// Keep connection alive with periodic pings
setInterval(() => {
    if (window.esAgentClient && window.esAgentClient.websocket && window.esAgentClient.isConnected) {
        window.esAgentClient.websocket.send(JSON.stringify({ type: 'ping' }));
    }
}, 30000); // 30 seconds