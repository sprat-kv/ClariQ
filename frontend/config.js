/**
 * G-SIA Frontend Configuration
 * Modify these settings to customize the frontend behavior
 */

window.GSIA_CONFIG = {
    // API Configuration
    api: {
        baseUrl: 'http://localhost:8000/api/v1',
        timeout: 30000, // 30 seconds
        retryAttempts: 3
    },

    // UI Configuration
    ui: {
        // Theme colors (CSS custom properties)
        colors: {
            primary: '#667eea',
            secondary: '#764ba2',
            success: '#10b981',
            warning: '#f59e0b',
            error: '#ef4444',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
        },

        // Animation settings
        animations: {
            enabled: true,
            duration: 300, // milliseconds
            easing: 'ease-out'
        },

        // Chat settings
        chat: {
            maxMessageLength: 1000,
            autoScroll: true,
            showTimestamps: true,
            maxRecentQueries: 10
        }
    },

    // Features Configuration
    features: {
        // Enable/disable specific features
        statusMonitoring: true,
        complianceStats: true,
        recentQueries: true,
        toastNotifications: true,
        autoResizeInput: true,
        characterCount: true
    },

    // Compliance Display
    compliance: {
        // Show detailed policy reasoning
        showPolicyReasoning: true,
        
        // Show confidence scores for rewritten queries
        showConfidence: true,
        
        // Compliance status colors
        statusColors: {
            allowed: '#10b981',
            rewritten: '#f59e0b',
            blocked: '#ef4444'
        }
    },

    // Monitoring Configuration
    monitoring: {
        // Health check interval (milliseconds)
        healthCheckInterval: 30000,
        
        // Status update interval (milliseconds)
        statusUpdateInterval: 30000,
        
        // Show detailed system status
        showDetailedStatus: true
    },

    // Development Settings
    development: {
        // Enable debug logging
        debug: false,
        
        // Mock mode for testing without backend
        mockMode: false,
        
        // Log API calls
        logApiCalls: false
    }
};

// Helper function to get config values
window.getConfig = function(path, defaultValue = null) {
    const keys = path.split('.');
    let value = window.GSIA_CONFIG;
    
    for (const key of keys) {
        if (value && typeof value === 'object' && key in value) {
            value = value[key];
        } else {
            return defaultValue;
        }
    }
    
    return value;
};

// Helper function to set config values
window.setConfig = function(path, value) {
    const keys = path.split('.');
    let config = window.GSIA_CONFIG;
    
    for (let i = 0; i < keys.length - 1; i++) {
        const key = keys[i];
        if (!(key in config) || typeof config[key] !== 'object') {
            config[key] = {};
        }
        config = config[key];
    }
    
    config[keys[keys.length - 1]] = value;
};

// Environment-specific overrides
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    // Development environment
    window.setConfig('development.debug', true);
    window.setConfig('development.logApiCalls', true);
} else {
    // Production environment
    window.setConfig('development.debug', false);
    window.setConfig('development.mockMode', false);
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = window.GSIA_CONFIG;
}