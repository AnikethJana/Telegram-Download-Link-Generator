// StreamBot Session Generator - Telegram Auth JavaScript
// This file provides additional helper functions for Telegram authentication

// Additional utility functions for the session generator
document.addEventListener('DOMContentLoaded', function() {
    console.log('Telegram Session Generator - JavaScript loaded');
    
    // Add any additional initialization code here
    initializeSessionGenerator();
});

function initializeSessionGenerator() {
    // Check if we're on the index page and configure Telegram widget
    const telegramContainer = document.getElementById('telegram-login-container');
    if (telegramContainer) {
        // Monitor for widget loading
        checkTelegramWidgetLoading();
    }
}

function checkTelegramWidgetLoading() {
    // Check if Telegram widget loaded successfully in a safe way
    let checkCount = 0;
    const maxChecks = 10;

    const isTrustedTelegramUrl = (urlStr) => {
        try {
            const url = new URL(urlStr);
            if (url.protocol !== 'https:') return false;
            const host = url.hostname.toLowerCase();
            // Allow exact telegram domains only
            const trustedHosts = new Set([
                'telegram.org',
                'www.telegram.org',
                'oauth.telegram.org',
                't.me',
                'www.t.me'
            ]);
            if (trustedHosts.has(host)) return true;
            // Also allow subdomains that end with .telegram.org (e.g., oauth.telegram.org)
            return host.endsWith('.telegram.org');
        } catch (_) {
            return false;
        }
    };

    const getTelegramWidgetIframe = () => {
        const iframes = document.querySelectorAll('iframe');
        for (const frame of iframes) {
            if (frame.src && isTrustedTelegramUrl(frame.src)) {
                return frame;
            }
        }
        return null;
    };

    const checkInterval = setInterval(() => {
        checkCount++;

        const widget = getTelegramWidgetIframe();
        const fallback = document.querySelector('.login-fallback');
        const placeholder = document.querySelector('.telegram-login-placeholder');

        if (widget) {
            // Widget loaded successfully
            clearInterval(checkInterval);
            console.log('Telegram login widget loaded successfully');
        } else if (checkCount >= maxChecks) {
            // Widget failed to load, show fallback
            clearInterval(checkInterval);
            if (fallback && !placeholder) {
                fallback.style.display = 'block';
                console.warn('Telegram login widget failed to load, showing fallback');
            }
        }
    }, 1000);
}

// Additional helper functions
function formatTimestamp(timestamp) {
    if (!timestamp) return 'Unknown';
    const date = new Date(timestamp * 1000);
    return date.toLocaleString();
}

function showNotification(message, type = 'info', duration = 5000) {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    // Add notification styles
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: white;
        padding: 16px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        border-left: 4px solid ${type === 'error' ? '#dc3545' : type === 'success' ? '#28a745' : '#007bff'};
        z-index: 1000;
        opacity: 0;
        transform: translateX(100%);
        transition: all 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(() => {
        notification.style.opacity = '1';
        notification.style.transform = 'translateX(0)';
    }, 100);
    
    // Auto remove
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, duration);
}

// Validation helpers
function validateTelegramData(data) {
    if (!data || typeof data !== 'object') {
        return false;
    }
    
    // Check required fields
    const requiredFields = ['id', 'auth_date', 'hash'];
    for (const field of requiredFields) {
        if (!data[field]) {
            console.error(`Missing required field: ${field}`);
            return false;
        }
    }
    
    // Check if auth_date is not too old (24 hours)
    const authDate = parseInt(data.auth_date);
    const currentTime = Math.floor(Date.now() / 1000);
    const maxAge = 24 * 60 * 60; // 24 hours
    
    if (currentTime - authDate > maxAge) {
        console.error('Authentication data is too old');
        return false;
    }
    
    return true;
}

// Export functions for global use
window.SessionGenerator = {
    showNotification,
    validateTelegramData,
    formatTimestamp
}; 