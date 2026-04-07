/**
 * Pool Metrics Dashboard Widget
 * 
 * Displays real-time connection pool health status and metrics.
 * Auto-refreshes every 30 seconds.
 * 
 * Usage: Include in dashboard template and call initPoolMetricsWidget()
 * 
 * Author: @cowdya
 * Version: 1.0.0
 * Created: 2026-03-02
 */

(function() {
    'use strict';

    // Configuration
    const REFRESH_INTERVAL_MS = 30000; // 30 seconds
    const API_ENDPOINT = '/api/v1/performance/pool/metrics/summary';
    
    // Health status thresholds
    const HEALTH_STATUS = {
        HEALTHY: 'healthy',
        DEGRADED: 'degraded',
        UNHEALTHY: 'unhealthy'
    };

    // DOM Elements
    let poolMetricsContainer = null;
    let lastUpdateElement = null;
    let statusIndicatorElement = null;
    let sqlUsageBarElement = null;
    let recommendationsListElement = null;

    /**
     * Initialize the Pool Metrics Widget
     */
    function initPoolMetricsWidget() {
        poolMetricsContainer = document.getElementById('pool-metrics-widget');
        if (!poolMetricsContainer) {
            console.warn('Pool Metrics Widget: Container #pool-metrics-widget not found');
            return;
        }

        // Create widget structure if not present
        if (poolMetricsContainer.children.length === 0) {
            createWidgetStructure();
        }

        // Cache DOM elements
        lastUpdateElement = document.getElementById('pool-metrics-last-update');
        statusIndicatorElement = document.getElementById('pool-metrics-status');
        sqlUsageBarElement = document.getElementById('pool-sql-usage-bar');
        recommendationsListElement = document.getElementById('pool-recommendations-list');

        // Initial fetch
        fetchPoolMetrics();

        // Set up auto-refresh
        setInterval(fetchPoolMetrics, REFRESH_INTERVAL_MS);
    }

    /**
     * Create widget HTML structure
     */
    function createWidgetStructure() {
        poolMetricsContainer.innerHTML = `
            <div class="pool-metrics-card">
                <div class="pool-metrics-header">
                    <h3>🔗 Connection Pool Health</h3>
                    <span id="pool-metrics-last-update" class="last-update">Updating...</span>
                </div>
                
                <div class="pool-metrics-body">
                    <div class="health-status">
                        <div id="pool-metrics-status" class="status-indicator status-healthy">
                            <span class="status-icon">●</span>
                            <span class="status-text">Healthy</span>
                        </div>
                    </div>
                    
                    <div class="sql-pool-metrics">
                        <div class="metric-label">
                            <span>SQL Pool Usage</span>
                            <span id="pool-sql-usage-text" class="metric-value">--%</span>
                        </div>
                        <div class="progress-bar">
                            <div id="pool-sql-usage-bar" class="progress-fill" style="width: 0%"></div>
                        </div>
                        <div class="metric-details">
                            <span id="pool-sql-active">--</span> / <span id="pool-sql-max">--</span> connections
                        </div>
                    </div>
                    
                    <div class="recommendations-section" id="recommendations-section" style="display: none;">
                        <h4>⚠️ Recommendations</h4>
                        <ul id="pool-recommendations-list" class="recommendations-list"></ul>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Fetch pool metrics from API
     */
    async function fetchPoolMetrics() {
        try {
            const response = await fetch(API_ENDPOINT, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': getApiKey()
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            updateWidget(data);
        } catch (error) {
            console.error('Pool Metrics Widget: Failed to fetch metrics', error);
            updateWidgetError(error.message);
        }
    }

    /**
     * Update widget with new data
     */
    function updateWidget(data) {
        if (!data || !data.health) {
            updateWidgetError('Invalid data received');
            return;
        }

        const health = data.health;
        const sqlPool = health.sql_pool;

        // Update last update time
        if (lastUpdateElement) {
            lastUpdateElement.textContent = `Updated: ${new Date().toLocaleTimeString()}`;
        }

        // Update health status
        if (statusIndicatorElement) {
            const statusClass = `status-${health.status}`;
            statusIndicatorElement.className = `status-indicator ${statusClass}`;
            
            const statusText = statusIndicatorElement.querySelector('.status-text');
            const statusIcon = statusIndicatorElement.querySelector('.status-icon');
            
            if (statusText) {
                statusText.textContent = health.status.charAt(0).toUpperCase() + health.status.slice(1);
            }
            if (statusIcon) {
                statusIcon.textContent = health.status === HEALTH_STATUS.HEALTHY ? '●' : 
                                         health.status === HEALTH_STATUS.DEGRADED ? '◐' : '●';
            }
        }

        // Update SQL pool usage
        if (sqlPool && sqlUsageBarElement) {
            const usagePct = sqlPool.usage_pct || 0;
            sqlUsageBarElement.style.width = `${Math.min(usagePct, 100)}%`;
            
            // Update color based on usage
            if (usagePct > 90) {
                sqlUsageBarElement.className = 'progress-fill progress-danger';
            } else if (usagePct > 75) {
                sqlUsageBarElement.className = 'progress-fill progress-warning';
            } else {
                sqlUsageBarElement.className = 'progress-fill progress-success';
            }

            // Update text values
            const usageTextElement = document.getElementById('pool-sql-usage-text');
            const activeElement = document.getElementById('pool-sql-active');
            const maxElement = document.getElementById('pool-sql-max');

            if (usageTextElement) usageTextElement.textContent = `${usagePct.toFixed(1)}%`;
            if (activeElement) activeElement.textContent = sqlPool.active || '--';
            if (maxElement) maxElement.textContent = sqlPool.max || '--';
        }

        // Update recommendations
        updateRecommendations(health.recommendations);
    }

    /**
     * Update recommendations section
     */
    function updateRecommendations(recommendations) {
        const sectionElement = document.getElementById('recommendations-section');
        
        if (!recommendations || recommendations.length === 0) {
            if (sectionElement) {
                sectionElement.style.display = 'none';
            }
            return;
        }

        if (sectionElement) {
            sectionElement.style.display = 'block';
        }

        if (recommendationsListElement) {
            recommendationsListElement.innerHTML = recommendations.map(rec => 
                `<li>${escapeHtml(rec)}</li>`
            ).join('');
        }
    }

    /**
     * Update widget with error state
     */
    function updateWidgetError(errorMessage) {
        if (lastUpdateElement) {
            lastUpdateElement.textContent = 'Error';
            lastUpdateElement.className = 'last-update error';
        }

        if (statusIndicatorElement) {
            statusIndicatorElement.className = 'status-indicator status-error';
            const statusText = statusIndicatorElement.querySelector('.status-text');
            if (statusText) {
                statusText.textContent = 'Error';
            }
        }

        if (recommendationsListElement) {
            recommendationsListElement.innerHTML = `<li class="error">Failed to load metrics: ${escapeHtml(errorMessage)}</li>`;
        }

        const sectionElement = document.getElementById('recommendations-section');
        if (sectionElement) {
            sectionElement.style.display = 'block';
        }
    }

    /**
     * Get API key from storage or meta tag
     */
    function getApiKey() {
        // Try to get from meta tag first
        const metaTag = document.querySelector('meta[name="api-key"]');
        if (metaTag) {
            return metaTag.getAttribute('content');
        }

        // Try localStorage
        const stored = localStorage.getItem('pilot_api_key');
        if (stored) {
            return stored;
        }

        // Fallback to empty (will fail, but that's okay)
        return '';
    }

    /**
     * Escape HTML to prevent XSS
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Export to global scope
    window.initPoolMetricsWidget = initPoolMetricsWidget;

    // Auto-init when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPoolMetricsWidget);
    } else {
        initPoolMetricsWidget();
    }
})();
