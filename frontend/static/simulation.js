/**
 * Bus Route Simulation Engine
 * Handles smooth animation of bus movement along ordered route links
 */

class SimulationManager {
    constructor() {
        this.orderedLinks = [];
        this.osrmRoutePath = null; // Continuous OSRM route path [[lat, lon], ...]
        this.currentLinkIndex = 0;
        this.progressInLink = 0.0; // 0.0 to 1.0
        this.progressInRoute = 0.0; // 0.0 to 1.0 for OSRM route
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
        this.lastDetectedLinkIndex = -1; // Track last detected link for triggering recommendations
        this.linkDetectionThreshold = 0.0005; // ~50 meters in degrees
    }

    /**
     * Initialize simulation with route data
     * @param {Array} orderedLinks - Ordered links for link detection
     * @param {Array} osrmRoutePath - Continuous OSRM route path [[lat, lon], ...] (optional)
     */
    initialize(orderedLinks, osrmRoutePath = null) {
        if (!orderedLinks || orderedLinks.length === 0) {
            console.error('Cannot initialize simulation: no links provided');
            return false;
        }
        
        this.orderedLinks = orderedLinks;
        this.osrmRoutePath = osrmRoutePath;
        this.reset();
        
        if (osrmRoutePath && osrmRoutePath.length > 0) {
            console.log(`Simulation initialized with ${orderedLinks.length} links and ${osrmRoutePath.length} OSRM route points`);
        } else {
            console.log(`Simulation initialized with ${orderedLinks.length} links (no OSRM route, using link-based movement)`);
        }
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
        this.progressInRoute = 0.0;
        this.visitedLinks = [];
        this.lastApiCallTime = 0;
        this.lastDetectedLinkIndex = -1;
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
     * Uses OSRM route path if available, otherwise falls back to link-based interpolation
     */
    getCurrentPosition() {
        // If OSRM route path is available, use it for smooth continuous movement
        if (this.osrmRoutePath && this.osrmRoutePath.length > 0) {
            return this._getPositionFromOSRMRoute();
        }
        
        // Fallback to link-based interpolation
        return this._getPositionFromLinks();
    }
    
    /**
     * Get position from continuous OSRM route path
     * @private
     */
    _getPositionFromOSRMRoute() {
        if (!this.osrmRoutePath || this.osrmRoutePath.length === 0) {
            return null;
        }
        
        // Clamp progress to [0, 1]
        const progress = Math.max(0, Math.min(1, this.progressInRoute));
        
        // Calculate index in route path
        const totalPoints = this.osrmRoutePath.length;
        const exactIndex = progress * (totalPoints - 1);
        const index = Math.floor(exactIndex);
        const fraction = exactIndex - index;
        
        // Get current and next point
        const currentPoint = this.osrmRoutePath[index];
        const nextPoint = index < totalPoints - 1 
            ? this.osrmRoutePath[index + 1] 
            : currentPoint;
        
        // Interpolate between points
        const lat = currentPoint[0] + (nextPoint[0] - currentPoint[0]) * fraction;
        const lon = currentPoint[1] + (nextPoint[1] - currentPoint[1]) * fraction;
        
        // Detect which link we're currently on/near
        const detectedLink = this._detectCurrentLink(lat, lon);
        
        return {
            lat: lat,
            lon: lon,
            linkIndex: detectedLink ? detectedLink.index : this.currentLinkIndex,
            progress: this.progressInRoute,
            link: detectedLink ? detectedLink.link : null,
            interpolating: false,
            detectedLink: detectedLink
        };
    }
    
    /**
     * Get position from discrete links (fallback method)
     * @private
     */
    _getPositionFromLinks() {
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
     * Calculate Haversine distance between two points in meters
     * @private
     */
    _haversineDistance(lat1, lon1, lat2, lon2) {
        const R = 6371000; // Earth radius in meters
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                  Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                  Math.sin(dLon / 2) * Math.sin(dLon / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
    }
    
    /**
     * Detect which link the bus is currently on/near based on position
     * @param {number} lat - Current latitude
     * @param {number} lon - Current longitude
     * @returns {Object|null} - Detected link info or null
     * @private
     */
    _detectCurrentLink(lat, lon) {
        if (!this.orderedLinks || this.orderedLinks.length === 0) {
            return null;
        }
        
        let closestLink = null;
        let closestDistance = Infinity;
        let closestIndex = -1;
        
        // Check distance to each link's midpoint
        for (let i = 0; i < this.orderedLinks.length; i++) {
            const link = this.orderedLinks[i];
            const startLat = parseFloat(link.StartLat);
            const startLon = parseFloat(link.StartLon);
            const endLat = parseFloat(link.EndLat);
            const endLon = parseFloat(link.EndLon);
            
            // Calculate midpoint
            const midLat = (startLat + endLat) / 2;
            const midLon = (startLon + endLon) / 2;
            
            // Calculate distance to midpoint
            const distance = this._haversineDistance(lat, lon, midLat, midLon);
            
            // Also check distance to start and end points
            const distToStart = this._haversineDistance(lat, lon, startLat, startLon);
            const distToEnd = this._haversineDistance(lat, lon, endLat, endLon);
            const minDistance = Math.min(distance, distToStart, distToEnd);
            
            if (minDistance < closestDistance) {
                closestDistance = minDistance;
                closestLink = link;
                closestIndex = i;
            }
        }
        
        // Return link if within threshold (50 meters)
        if (closestLink && closestDistance <= 50) {
            return {
                link: closestLink,
                index: closestIndex,
                distance: closestDistance
            };
        }
        
        return null;
    }

    /**
     * Get simulation state
     */
    getState() {
        const progress = this.osrmRoutePath && this.osrmRoutePath.length > 0
            ? this.progressInRoute
            : this.currentLinkIndex / Math.max(1, this.orderedLinks.length - 1);
            
        return {
            isRunning: this.isRunning,
            isPaused: this.isPaused,
            currentLinkIndex: this.currentLinkIndex,
            totalLinks: this.orderedLinks.length,
            progress: progress,
            speedMultiplier: this.speedMultiplier,
            visitedLinks: this.visitedLinks,
            usingOSRMRoute: this.osrmRoutePath && this.osrmRoutePath.length > 0
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

        // Update progress based on whether we're using OSRM route or links
        if (this.osrmRoutePath && this.osrmRoutePath.length > 0) {
            // Use OSRM route: progress along continuous path
            // Calculate total route time based on number of points (rough estimate)
            const routePoints = this.osrmRoutePath.length;
            const totalRouteTime = (routePoints / 10) * this.baseTraversalTime; // ~10 points per link
            const routeProgressIncrement = (deltaTime / (totalRouteTime / this.speedMultiplier));
            
            this.progressInRoute += routeProgressIncrement;
            
            // Check if route is complete
            if (this.progressInRoute >= 1.0) {
                this.progressInRoute = 1.0;
                this._handleRouteComplete();
                return;
            }
        } else {
            // Fallback to link-based progress
            this.progressInLink += progressIncrement;

            // Check if we've completed the current link
            if (this.progressInLink >= 1.0) {
                this._advanceToNextLink();
            }
        }

        // Notify position update (this will also check for link changes)
        this._notifyPositionUpdate();

        // Check if we should make an API call (fallback periodic check)
        if (currentTime - this.lastApiCallTime >= this.apiCallInterval) {
            this.lastApiCallTime = currentTime;
            // Position update notification will trigger API call if needed
        }

        // Continue animation
        this.animationFrameId = requestAnimationFrame(() => this._animate());
    }
    
    /**
     * Handle route completion
     * @private
     */
    _handleRouteComplete() {
        console.log('Simulation complete!');
        this.stop();
        
        if (this.onComplete) {
            this.onComplete();
        }
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
     * Also checks for link changes when using OSRM route
     * @private
     */
    _notifyPositionUpdate() {
        if (this.onPositionUpdate) {
            const position = this.getCurrentPosition();
            if (position) {
                // If using OSRM route and we detected a link, check if it's a new link
                if (this.osrmRoutePath && position.detectedLink) {
                    const detectedIndex = position.detectedLink.index;
                    
                    // If we detected a new link, trigger link change callback
                    if (detectedIndex !== this.lastDetectedLinkIndex && detectedIndex >= 0) {
                        this.lastDetectedLinkIndex = detectedIndex;
                        this.currentLinkIndex = detectedIndex;
                        
                        // Add to visited links if not already there
                        if (!this.visitedLinks.includes(detectedIndex)) {
                            this.visitedLinks.push(detectedIndex);
                        }
                        
                        // Notify link change
                        if (this.onLinkChange) {
                            const link = position.detectedLink.link;
                            this.onLinkChange(detectedIndex, link);
                        }
                    }
                }
                
                this.onPositionUpdate(position);
            }
        }
    }
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SimulationManager;
}
