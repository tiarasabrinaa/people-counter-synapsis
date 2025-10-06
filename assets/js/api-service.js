/**
 * API Service for People Counting System
 * Handles all API calls to backend
 */

const API_BASE_URL = 'http://localhost:8000';

class APIService {
    constructor(baseUrl = API_BASE_URL) {
        this.baseUrl = baseUrl;
    }

    /**
     * Generic fetch wrapper with error handling
     */
    async fetch(endpoint, options = {}) {
        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API Error (${endpoint}):`, error);
            throw error;
        }
    }

    /**
     * Get live statistics (last 5 minutes)
     */
    async getLiveStats(areaName = null) {
        const params = areaName ? `?area_name=${areaName}` : '';
        return await this.fetch(`/api/stats/live${params}`);
    }

    /**
     * Get historical statistics
     * @param {Object} params - Query parameters
     * @param {number} params.hours - Hours to look back (default: 24)
     * @param {boolean} params.include_hourly - Include hourly breakdown
     * @param {string} params.area_name - Filter by area name
     */
    async getStats(params = {}) {
        const queryParams = new URLSearchParams({
            hours: params.hours || 24,
            include_hourly: params.include_hourly !== false,
            ...(params.area_name && { area_name: params.area_name })
        });

        return await this.fetch(`/api/stats/?${queryParams}`);
    }

    /**
     * Get detection records
     */
    async getDetections(params = {}) {
        const queryParams = new URLSearchParams({
            limit: params.limit || 100,
            skip: params.skip || 0,
            ...(params.area_name && { area_name: params.area_name }),
            ...(params.track_id && { track_id: params.track_id })
        });

        return await this.fetch(`/api/stats/detections?${queryParams}`);
    }

    /**
     * Get counting events
     */
    async getEvents(params = {}) {
        const queryParams = new URLSearchParams({
            limit: params.limit || 100,
            skip: params.skip || 0,
            ...(params.area_name && { area_name: params.area_name }),
            ...(params.event_type && { event_type: params.event_type })
        });

        return await this.fetch(`/api/stats/events?${queryParams}`);
    }

    /**
     * Generate forecast
     */
    async getForecast(areaName = null, periods = 24) {
        return await this.fetch('/api/stats/forecast', {
            method: 'POST',
            body: JSON.stringify({
                area_name: areaName,
                periods: periods
            })
        });
    }

    /**
     * Get all polygon areas
     */
    async getAreas() {
        return await this.fetch('/api/config/areas');
    }

    /**
     * Get specific area
     */
    async getArea(areaName) {
        return await this.fetch(`/api/config/area/${areaName}`);
    }

    /**
     * Create new area
     */
    async createArea(data) {
        return await this.fetch('/api/config/area', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    /**
     * Update area
     */
    async updateArea(areaName, data) {
        return await this.fetch(`/api/config/area/${areaName}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    /**
     * Check API health
     */
    async checkHealth() {
        return await this.fetch('/health');
    }
}

// Export singleton instance
const apiService = new APIService();