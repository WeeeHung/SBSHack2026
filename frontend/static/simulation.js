/**
 * Bus Route Simulation Engine
 * Handles smooth animation of bus movement along ordered route links
 */

class SimulationManager {
    constructor() {
        this.orderedLinks = [];
        this.currentLinkIndex = 0;
        this.progressInLink = 0.0; // 0.0 to 1.0
        this.isRunning = false;
        this.isPaused = false;
        this.speedMultiplier = 1.0;
        this.animationFrameId = null;
        this.lastUpdateTime = null;
        this.baseTraversalTime = 3000; // 3 seconds per link at 1x speed (in ms)
        this.lastApiCallTime = 0;
        this.apiCallInterval = 3000; // Call API every 3 seconds
        this.onPositionUpdate = null; // Callback for position updates
        this.onLinkChange = null; // Callback when moving to new link
        this.onComplete = null; // Callback when simulation completes
        this.visitedLinks = []; // Track visited links for trail
    }

    /**
     * Initialize simulation with route data
     */
    initialize(orderedLinks) {
        if (!orderedLinks || orderedLinks.length === 0) {
            console.error('Cannot initialize simulation: no links provided');
            return false;
        }
        
        this.orderedLinks = orderedLinks;
        this.reset();
        console.log(`Simulation initialized with ${orderedLinks.length} links`);
        return true;
    }

    /**
     * Start or resume the simulation
     */
    start() {
        if (!this.orderedLinks || this.orderedLinks.length === 0) {
            console.error('Cannot start simulation: not initialized');
            return;
        }

        if (this.isRunning && !this.isPaused) {
            console.log('Simulation already running');
            return;
        }

        this.isRunning = true;
        this.isPaused = false;
        this.lastUpdateTime = performance.now();
        this.lastApiCallTime = performance.now();
        
        console.log(`Simulation started at link ${this.currentLinkIndex} (speed: ${this.speedMultiplier}x)`);
        
        // Trigger initial position update
        this._notifyPositionUpdate();
        
        // Start animation loop
        this._animate();
    }

    /**
     * Pause the simulation
     */
    pause() {
        if (!this.isRunning || this.isPaused) {
            return;
        }

        this.isPaused = true;
        console.log('Simulation paused');
        
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
    }

    /**
     * Resume the simulation
     */
    resume() {
        if (!this.isRunning || !this.isPaused) {
            return;
        }

        this.isPaused = false;
        this.lastUpdateTime = performance.now();
        console.log('Simulation resumed');
        this._animate();
    }

    /**
     * Stop the simulation completely
     */
    stop() {
        this.isRunning = false;
        this.isPaused = false;
        
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
        
        console.log('Simulation stopped');
    }

    /**
     * Reset simulation to the beginning
     */
    reset() {
        this.stop();
        this.currentLinkIndex = 0;
        this.progressInLink = 0.0;
        this.visitedLinks = [];
        this.lastApiCallTime = 0;
        console.log('Simulation reset');
    }

    /**
     * Set simulation speed multiplier
     */
    setSpeed(multiplier) {
        if (multiplier <= 0) {
            console.error('Speed multiplier must be positive');
            return;
        }
        
        this.speedMultiplier = multiplier;
        console.log(`Simulation speed set to ${multiplier}x`);
    }

    /**
     * Jump to a specific link
     */
    jumpToLink(linkIndex) {
        if (linkIndex < 0 || linkIndex >= this.orderedLinks.length) {
            console.error(`Invalid link index: ${linkIndex}`);
            return;
        }

        const wasRunning = this.isRunning && !this.isPaused;
        
        if (wasRunning) {
            this.pause();
        }

        this.currentLinkIndex = linkIndex;
        this.progressInLink = 0.0;
        
        // Update visited links
        this.visitedLinks = [];
        for (let i = 0; i < linkIndex; i++) {
            this.visitedLinks.push(i);
        }
        
        console.log(`Jumped to link ${linkIndex}`);
        
        this._notifyPositionUpdate();
        
        if (wasRunning) {
            this.resume();
        }
    }

    /**
     * Get current interpolated position
     */
    getCurrentPosition() {
        if (!this.orderedLinks || this.orderedLinks.length === 0) {
            return null;
        }

        const currentLink = this.orderedLinks[this.currentLinkIndex];
        if (!currentLink) {
            return null;
        }

        const startLat = parseFloat(currentLink.StartLat);
        const startLon = parseFloat(currentLink.StartLon);
        const endLat = parseFloat(currentLink.EndLat);
        const endLon = parseFloat(currentLink.EndLon);

        // Check if we need to interpolate to next link (for gaps between links)
        if (this.progressInLink >= 1.0 && this.currentLinkIndex + 1 < this.orderedLinks.length) {
            const nextLink = this.orderedLinks[this.currentLinkIndex + 1];
            const nextStartLat = parseFloat(nextLink.StartLat);
            const nextStartLon = parseFloat(nextLink.StartLon);
            
            // Calculate distance between current end and next start
            const gap = this._calculateDistance(endLat, endLon, nextStartLat, nextStartLon);
            
            // If gap exists (> 1 meter), interpolate during the overage
            if (gap > 0.00001) { // ~1 meter threshold
                const overage = this.progressInLink - 1.0;
                const interpolationProgress = Math.min(overage * 10, 1.0); // Use 10% of link time for gap
                
                if (interpolationProgress < 1.0) {
                    // Interpolate between current end and next start
                    const lat = endLat + (nextStartLat - endLat) * interpolationProgress;
                    const lon = endLon + (nextStartLon - endLon) * interpolationProgress;
                    
                    return {
                        lat: lat,
                        lon: lon,
                        linkIndex: this.currentLinkIndex,
                        progress: this.progressInLink,
                        link: currentLink,
                        interpolating: true
                    };
                }
            }
        }

        // Normal interpolation within the current link
        const lat = startLat + (endLat - startLat) * Math.min(this.progressInLink, 1.0);
        const lon = startLon + (endLon - startLon) * Math.min(this.progressInLink, 1.0);

        return {
            lat: lat,
            lon: lon,
            linkIndex: this.currentLinkIndex,
            progress: this.progressInLink,
            link: currentLink,
            interpolating: false
        };
    }

    /**
     * Calculate euclidean distance between two points
     * @private
     */
    _calculateDistance(lat1, lon1, lat2, lon2) {
        // Simple euclidean distance for small gaps
        const dLat = lat2 - lat1;
        const dLon = lon2 - lon1;
        return Math.sqrt(dLat * dLat + dLon * dLon);
    }

    /**
     * Get simulation state
     */
    getState() {
        return {
            isRunning: this.isRunning,
            isPaused: this.isPaused,
            currentLinkIndex: this.currentLinkIndex,
            totalLinks: this.orderedLinks.length,
            progress: this.currentLinkIndex / Math.max(1, this.orderedLinks.length - 1),
            speedMultiplier: this.speedMultiplier,
            visitedLinks: this.visitedLinks
        };
    }

    /**
     * Animation loop
     * @private
     */
    _animate() {
        if (!this.isRunning || this.isPaused) {
            return;
        }

        const currentTime = performance.now();
        const deltaTime = currentTime - this.lastUpdateTime;
        this.lastUpdateTime = currentTime;

        // Calculate progress increment based on speed
        const traversalTime = this.baseTraversalTime / this.speedMultiplier;
        const progressIncrement = deltaTime / traversalTime;

        // Update progress
        this.progressInLink += progressIncrement;

        // Check if we've completed the current link
        if (this.progressInLink >= 1.0) {
            this._advanceToNextLink();
        }

        // Notify position update
        this._notifyPositionUpdate();

        // Check if we should make an API call
        if (currentTime - this.lastApiCallTime >= this.apiCallInterval) {
            this.lastApiCallTime = currentTime;
            // Position update notification will trigger API call
        }

        // Continue animation
        this.animationFrameId = requestAnimationFrame(() => this._animate());
    }

    /**
     * Advance to the next link in the route
     * @private
     */
    _advanceToNextLink() {
        // Check if there's a gap to next link that needs interpolation
        if (this.currentLinkIndex + 1 < this.orderedLinks.length) {
            const currentLink = this.orderedLinks[this.currentLinkIndex];
            const nextLink = this.orderedLinks[this.currentLinkIndex + 1];
            
            const gap = this._calculateDistance(
                parseFloat(currentLink.EndLat),
                parseFloat(currentLink.EndLon),
                parseFloat(nextLink.StartLat),
                parseFloat(nextLink.StartLon)
            );
            
            // If significant gap exists, allow progress to go beyond 1.0 for interpolation
            if (gap > 0.00001 && this.progressInLink < 1.1) {
                return; // Continue interpolating across the gap
            }
        }
        
        // Add current link to visited
        this.visitedLinks.push(this.currentLinkIndex);

        // Move to next link
        this.currentLinkIndex++;
        this.progressInLink = 0.0;

        // Check if simulation is complete
        if (this.currentLinkIndex >= this.orderedLinks.length) {
            console.log('Simulation complete!');
            this.stop();
            this.currentLinkIndex = this.orderedLinks.length - 1; // Stay at last link
            
            if (this.onComplete) {
                this.onComplete();
            }
            return;
        }

        console.log(`Advanced to link ${this.currentLinkIndex}/${this.orderedLinks.length}`);

        // Notify link change
        if (this.onLinkChange) {
            const currentLink = this.orderedLinks[this.currentLinkIndex];
            this.onLinkChange(this.currentLinkIndex, currentLink);
        }
    }

    /**
     * Notify listeners of position update
     * @private
     */
    _notifyPositionUpdate() {
        if (this.onPositionUpdate) {
            const position = this.getCurrentPosition();
            if (position) {
                this.onPositionUpdate(position);
            }
        }
    }
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SimulationManager;
}
