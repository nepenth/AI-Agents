/**
 * Centralized Duration Formatting Service
 * Eliminates duplicate formatDuration() methods across 5 files
 */
class DurationFormatter {
    /**
     * Format duration from milliseconds to human-readable string
     * @param {number} milliseconds - Duration in milliseconds
     * @param {Object} options - Formatting options
     * @param {boolean} options.showSeconds - Include seconds in output (default: true)
     * @param {boolean} options.compact - Use compact format (1h 30m vs 1 hour 30 minutes)
     * @param {string} options.fallback - Fallback text for invalid durations (default: '--')
     * @returns {string} Formatted duration string
     */
    static format(milliseconds, options = {}) {
        const {
            showSeconds = true,
            compact = true,
            fallback = '--'
        } = options;

        // Handle invalid inputs
        if (!milliseconds || milliseconds <= 0 || !isFinite(milliseconds)) {
            return fallback;
        }

        const seconds = Math.floor(milliseconds / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        const remainingHours = hours % 24;
        const remainingMinutes = minutes % 60;
        const remainingSeconds = seconds % 60;

        const parts = [];

        // Add days if present
        if (days > 0) {
            parts.push(compact ? `${days}d` : `${days} day${days !== 1 ? 's' : ''}`);
        }

        // Add hours if present
        if (remainingHours > 0) {
            parts.push(compact ? `${remainingHours}h` : `${remainingHours} hour${remainingHours !== 1 ? 's' : ''}`);
        }

        // Add minutes if present
        if (remainingMinutes > 0) {
            parts.push(compact ? `${remainingMinutes}m` : `${remainingMinutes} minute${remainingMinutes !== 1 ? 's' : ''}`);
        }

        // Add seconds if enabled and present (or if it's the only unit)
        if (showSeconds && (remainingSeconds > 0 || parts.length === 0)) {
            parts.push(compact ? `${remainingSeconds}s` : `${remainingSeconds} second${remainingSeconds !== 1 ? 's' : ''}`);
        }

        return parts.length > 0 ? parts.join(' ') : fallback;
    }

    /**
     * Format duration from seconds to human-readable string
     * @param {number} seconds - Duration in seconds
     * @param {Object} options - Formatting options
     * @returns {string} Formatted duration string
     */
    static formatSeconds(seconds, options = {}) {
        return this.format(seconds * 1000, options);
    }

    /**
     * Format duration from minutes to human-readable string
     * @param {number} minutes - Duration in minutes
     * @param {Object} options - Formatting options
     * @returns {string} Formatted duration string
     */
    static formatMinutes(minutes, options = {}) {
        // Handle fractional minutes for sub-minute durations
        if (minutes < 1) {
            const seconds = Math.round(minutes * 60);
            return options.compact !== false ? `${seconds}s` : `${seconds} second${seconds !== 1 ? 's' : ''}`;
        }
        return this.format(minutes * 60 * 1000, options);
    }

    /**
     * Format ETC (Estimated Time to Completion) with special handling
     * @param {number} milliseconds - Duration in milliseconds
     * @param {Object} options - Formatting options
     * @returns {string} Formatted ETC string with "ETC: " prefix
     */
    static formatETC(milliseconds, options = {}) {
        const formatted = this.format(milliseconds, { ...options, fallback: '--' });
        return formatted === '--' ? '--' : `ETC: ${formatted}`;
    }

    /**
     * Format elapsed time with special handling
     * @param {number} milliseconds - Duration in milliseconds
     * @param {Object} options - Formatting options
     * @returns {string} Formatted elapsed time string
     */
    static formatElapsed(milliseconds, options = {}) {
        return this.format(milliseconds, { ...options, fallback: '0s' });
    }
}

// Make available globally
window.DurationFormatter = DurationFormatter;

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DurationFormatter;
}