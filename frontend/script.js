/**
 * G-SIA Frontend JavaScript
 * Handles chat interface, API integration, and UI interactions
 */

class GSIAFrontend {
    constructor() {
        this.apiBaseUrl = 'http://localhost:8000/api/v1';
        this.isConnected = false;
        this.recentQueries = [];
        this.complianceStats = {
            allowed: 0,
            rewritten: 0,
            blocked: 0
        };
        
        this.initializeElements();
        this.bindEvents();
        this.initializeApp();
    }

    initializeElements() {
        // Core elements
        this.chatForm = document.getElementById('chatForm');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.chatMessages = document.getElementById('chatMessages');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.toastContainer = document.getElementById('toastContainer');
        
        // Status elements
        this.statusIndicator = document.getElementById('statusIndicator');
        this.statusDot = this.statusIndicator.querySelector('.status-dot');
        this.statusText = this.statusIndicator.querySelector('.status-text');
        
        // Sidebar elements
        this.systemStatusCard = document.getElementById('systemStatusCard');
        this.databaseStatusCard = document.getElementById('databaseStatusCard');
        this.aiStatusCard = document.getElementById('aiStatusCard');
        this.recentQueriesContainer = document.getElementById('recentQueries');
        this.allowedCount = document.getElementById('allowedCount');
        this.rewrittenCount = document.getElementById('rewrittenCount');
        this.blockedCount = document.getElementById('blockedCount');
        
        // Character count
        this.charCount = document.getElementById('charCount');
    }

    bindEvents() {
        // Chat form submission
        this.chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendMessage();
        });

        // Message input events
        this.messageInput.addEventListener('input', () => {
            this.updateCharCount();
            this.adjustTextareaHeight();
        });

        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        this.messageInput.addEventListener('focus', () => {
            this.adjustTextareaHeight();
        });
    }

    async initializeApp() {
        try {
            // Check system status
            await this.checkSystemStatus();
            
            // Start periodic status checks
            this.startStatusMonitoring();
            
            // Load initial data
            await this.loadComplianceStats();
            
        } catch (error) {
            console.error('Failed to initialize app:', error);
            this.showToast('error', 'Initialization Failed', 'Could not connect to G-SIA system');
        }
    }

    async checkSystemStatus() {
        try {
            const response = await this.apiCall('/health');
            
            if (response.status === 'healthy') {
                this.updateConnectionStatus(true);
                this.updateSystemStatus(response);
            } else {
                this.updateConnectionStatus(false);
            }
        } catch (error) {
            console.error('Health check failed:', error);
            this.updateConnectionStatus(false);
        }
    }

    updateConnectionStatus(connected) {
        this.isConnected = connected;
        
        if (connected) {
            this.statusDot.className = 'status-dot connected';
            this.statusText.textContent = 'Connected';
        } else {
            this.statusDot.className = 'status-dot error';
            this.statusText.textContent = 'Disconnected';
        }
    }

    updateSystemStatus(healthData) {
        const components = healthData.components || {};
        
        // Update system status
        this.updateStatusCard(this.systemStatusCard, 
            components.orchestrator === 'ready' ? 'ready' : 'error',
            components.orchestrator === 'ready' ? 'Ready' : 'Error'
        );
        
        // Update database status
        this.updateStatusCard(this.databaseStatusCard,
            components.database === 'ready' ? 'ready' : 'error',
            components.database === 'ready' ? 'Ready' : 'Error'
        );
        
        // Update AI status
        this.updateStatusCard(this.aiStatusCard,
            components.policy_agent === 'healthy' && components.sql_agent === 'healthy' ? 'ready' : 'error',
            components.policy_agent === 'healthy' && components.sql_agent === 'healthy' ? 'Ready' : 'Error'
        );
    }

    updateStatusCard(card, status, text) {
        const statusValue = card.querySelector('.status-value');
        statusValue.textContent = text;
        statusValue.className = `status-value ${status}`;
    }

    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message) return;

        // Add user message to chat
        this.addMessageToChat('user', message);
        
        // Clear input
        this.messageInput.value = '';
        this.updateCharCount();
        this.adjustTextareaHeight();
        
        // Show loading
        this.showLoading(true);
        
        try {
            // Send to API
            const response = await this.apiCall('/query', {
                method: 'POST',
                body: JSON.stringify({
                    query: message,
                    context: null,
                    metadata: {
                        source: 'web_interface',
                        timestamp: new Date().toISOString()
                    }
                })
            });

            // Add AI response to chat
            this.addAIResponseToChat(response);
            
            // Update stats
            this.updateComplianceStats(response.compliance_status);
            
            // Add to recent queries
            this.addToRecentQueries(message, response);
            
        } catch (error) {
            console.error('Failed to send message:', error);
            this.addErrorMessageToChat(error.message || 'Failed to process your query');
            this.showToast('error', 'Query Failed', 'Could not process your request');
        } finally {
            this.showLoading(false);
        }
    }

    addMessageToChat(type, content, data = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;
        
        let avatarIcon, avatarClass;
        switch (type) {
            case 'user':
                avatarIcon = 'fas fa-user';
                avatarClass = 'user-message';
                break;
            case 'ai':
                avatarIcon = 'fas fa-robot';
                avatarClass = 'ai-message';
                break;
            case 'system':
                avatarIcon = 'fas fa-info-circle';
                avatarClass = 'system-message';
                break;
            case 'error':
                avatarIcon = 'fas fa-exclamation-triangle';
                avatarClass = 'error-message';
                break;
        }
        
        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="message-avatar">
                    <i class="${avatarIcon}"></i>
                </div>
                <div class="message-text">
                    ${this.formatMessageContent(content, data)}
                </div>
            </div>
        `;
        
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    formatMessageContent(content, data) {
        if (typeof content === 'string') {
            return `<p>${this.escapeHtml(content)}</p>`;
        }
        
        // Handle structured data
        let html = '';
        
        if (data && data.result) {
            if (data.compliance_status === 'ALLOWED') {
                html += this.formatAllowedResult(data.result);
            } else if (data.compliance_status === 'REWRITTEN') {
                html += this.formatRewrittenResult(data.result);
            } else if (data.compliance_status === 'BLOCKED') {
                html += this.formatBlockedResult(data.result);
            }
        }
        
        // Add compliance badge
        html += this.createComplianceBadge(data.compliance_status, data.policy_reasoning);
        
        return html;
    }

    formatAllowedResult(result) {
        let html = '<p><strong>Query Results:</strong></p>';
        
        if (result.data && Array.isArray(result.data)) {
            if (result.data.length === 0) {
                html += '<p>No results found for your query.</p>';
            } else {
                html += '<div class="results-table">';
                html += '<table style="width: 100%; border-collapse: collapse; margin-top: 0.5rem;">';
                
                // Create table headers from first row
                const headers = Object.keys(result.data[0]);
                html += '<tr>';
                headers.forEach(header => {
                    html += `<th style="text-align: left; padding: 0.5rem; border-bottom: 1px solid #ddd;">${this.escapeHtml(header)}</th>`;
                });
                html += '</tr>';
                
                // Add data rows
                result.data.forEach(row => {
                    html += '<tr>';
                    headers.forEach(header => {
                        html += `<td style="padding: 0.5rem; border-bottom: 1px solid #eee;">${this.escapeHtml(String(row[header]))}</td>`;
                    });
                    html += '</tr>';
                });
                
                html += '</table>';
                html += '</div>';
                
                if (result.row_count) {
                    html += `<p><em>Total rows: ${result.row_count}</em></p>`;
                }
            }
        }
        
        return html;
    }

    formatRewrittenResult(result) {
        let html = '<p><strong>Query Modified for Compliance:</strong></p>';
        html += `<p><em>"${this.escapeHtml(result.rewritten_query)}"</em></p>`;
        
        if (result.reasoning) {
            html += `<p><strong>Reasoning:</strong> ${this.escapeHtml(result.reasoning)}</p>`;
        }
        
        if (result.confidence) {
            html += `<p><strong>Confidence:</strong> ${(result.confidence * 100).toFixed(1)}%</p>`;
        }
        
        return html;
    }

    formatBlockedResult(result) {
        let html = '<p><strong>Query Blocked for Compliance:</strong></p>';
        
        if (result.blocked_reason) {
            html += `<p>${this.escapeHtml(result.blocked_reason)}</p>`;
        }
        
        if (result.regulation) {
            html += `<p><strong>Regulation:</strong> ${this.escapeHtml(result.regulation)}</p>`;
        }
        
        return html;
    }

    createComplianceBadge(status, reasoning) {
        const statusClass = status.toLowerCase();
        const statusText = status.charAt(0) + status.slice(1).toLowerCase();
        
        return `
            <div class="compliance-badge ${statusClass}">
                <i class="fas fa-shield-check"></i>
                <span>${statusText}</span>
            </div>
        `;
    }

    addAIResponseToChat(response) {
        if (response.success) {
            this.addMessageToChat('ai', 'AI Response', response);
        } else {
            this.addErrorMessageToChat('AI processing failed');
        }
    }

    addErrorMessageToChat(message) {
        this.addMessageToChat('error', message);
    }

    updateComplianceStats(status) {
        if (status === 'ALLOWED') {
            this.complianceStats.allowed++;
        } else if (status === 'REWRITTEN') {
            this.complianceStats.rewritten++;
        } else if (status === 'BLOCKED') {
            this.complianceStats.blocked++;
        }
        
        this.updateComplianceStatsDisplay();
    }

    updateComplianceStatsDisplay() {
        this.allowedCount.textContent = this.complianceStats.allowed;
        this.rewrittenCount.textContent = this.complianceStats.rewritten;
        this.blockedCount.textContent = this.complianceStats.blocked;
    }

    addToRecentQueries(query, response) {
        const queryItem = {
            text: query,
            status: response.compliance_status,
            timestamp: new Date(),
            workflowId: response.workflow_id
        };
        
        this.recentQueries.unshift(queryItem);
        
        // Keep only last 10 queries
        if (this.recentQueries.length > 10) {
            this.recentQueries.pop();
        }
        
        this.updateRecentQueriesDisplay();
    }

    updateRecentQueriesDisplay() {
        if (this.recentQueries.length === 0) {
            this.recentQueriesContainer.innerHTML = '<p class="no-queries">No queries yet</p>';
            return;
        }
        
        this.recentQueriesContainer.innerHTML = this.recentQueries.map(query => `
            <div class="query-item" onclick="frontend.replayQuery('${query.workflowId}')">
                <div class="query-text">${this.escapeHtml(query.text)}</div>
                <div class="query-meta">
                    <span class="compliance-badge ${query.status.toLowerCase()}">${query.status}</span>
                    <span>${this.formatTimestamp(query.timestamp)}</span>
                </div>
            </div>
        `).join('');
    }

    async replayQuery(workflowId) {
        // This could be enhanced to replay the exact query
        this.showToast('info', 'Replay Feature', 'Query replay functionality coming soon!');
    }

    async loadComplianceStats() {
        try {
            const response = await this.apiCall('/status/metrics');
            if (response.data && response.data.query_statistics) {
                const stats = response.data.query_statistics.compliance_decisions;
                this.complianceStats = {
                    allowed: stats.allowed || 0,
                    rewritten: stats.rewritten || 0,
                    blocked: stats.blocked || 0
                };
                this.updateComplianceStatsDisplay();
            }
        } catch (error) {
            console.error('Failed to load compliance stats:', error);
        }
    }

    startStatusMonitoring() {
        // Check status every 30 seconds
        setInterval(() => {
            this.checkSystemStatus();
        }, 30000);
    }

    async apiCall(endpoint, options = {}) {
        const url = `${this.apiBaseUrl}${endpoint}`;
        
        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer test-token' // For development
            }
        };
        
        const finalOptions = { ...defaultOptions, ...options };
        
        try {
            const response = await fetch(url, finalOptions);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error(`API call failed for ${endpoint}:`, error);
            throw error;
        }
    }

    showLoading(show) {
        if (show) {
            this.loadingOverlay.classList.add('show');
            this.sendButton.disabled = true;
        } else {
            this.loadingOverlay.classList.remove('show');
            this.sendButton.disabled = false;
        }
    }

    showToast(type, title, message) {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const iconMap = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };
        
        toast.innerHTML = `
            <i class="toast-icon ${iconMap[type]}"></i>
            <div class="toast-content">
                <div class="toast-title">${this.escapeHtml(title)}</div>
                <div class="toast-message">${this.escapeHtml(message)}</div>
            </div>
            <button class="toast-close" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        this.toastContainer.appendChild(toast);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, 5000);
    }

    updateCharCount() {
        const count = this.messageInput.value.length;
        this.charCount.textContent = `${count}/1000`;
        
        // Change color based on count
        if (count > 900) {
            this.charCount.style.color = '#ef4444';
        } else if (count > 800) {
            this.charCount.style.color = '#f59e0b';
        } else {
            this.charCount.style.color = '#666';
        }
    }

    adjustTextareaHeight() {
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 120) + 'px';
    }

    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatTimestamp(date) {
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) { // Less than 1 minute
            return 'Just now';
        } else if (diff < 3600000) { // Less than 1 hour
            const minutes = Math.floor(diff / 60000);
            return `${minutes}m ago`;
        } else if (diff < 86400000) { // Less than 1 day
            const hours = Math.floor(diff / 3600000);
            return `${hours}h ago`;
        } else {
            return date.toLocaleDateString();
        }
    }
}

// Initialize the frontend when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.frontend = new GSIAFrontend();
});

// Export for potential module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = GSIAFrontend;
}