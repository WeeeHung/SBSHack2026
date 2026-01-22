// Configuration
const API_BASE_URL = 'http://localhost:8000';
let updateInterval = null;
let lastAction = null;
let speechSynthesis = null;

// Map variables
let map = null;
let busMarker = null;
let routeLayer = null;
let routePreviewLayer = null;
let clickMarker = null;
let currentLinkLayer = null;
let nextLinksLayer = null;
let inboundLinksLayer = null;
let outboundLinksLayer = null;
let trailLayer = null;

// Layer visibility state
let showRoute = true;
let showInbound = true;
let showOutbound = true;
let autoFollow = true;

// Current data
let currentMapData = null;

// Simulation variables
let simulationManager = null;
let isDemoMode = false;
let simulationRouteData = null;
let lastSimulationApiCall = 0;
const SIMULATION_API_INTERVAL = 3000; // Call API every 3 seconds (fallback)
let isWaitingForVoice = false;
let lastLinkIndexForRecommendation = -1; // Track last link that triggered recommendation

// DOM Elements
const elements = {
    actionIndicator: document.getElementById('actionIndicator'),
    actionIcon: document.getElementById('actionIcon'),
    actionText: document.getElementById('actionText'),
    currentSpeed: document.getElementById('currentSpeed'),
    predictedSpeed: document.getElementById('predictedSpeed'),
    reasoning: document.getElementById('reasoning'),
    rainIndicator: document.getElementById('rainIndicator'),
    incidentIndicator: document.getElementById('incidentIndicator'),
    busNo: document.getElementById('busNo'),
    direction: document.getElementById('direction'),
    latitude: document.getElementById('latitude'),
    longitude: document.getElementById('longitude'),
    loadRouteBtn: document.getElementById('loadRouteBtn'),
    getLocationBtn: document.getElementById('getLocationBtn'),
    startBtn: document.getElementById('startBtn'),
    stopBtn: document.getElementById('stopBtn'),
    voiceEnabled: document.getElementById('voiceEnabled'),
    updateIntervalInput: document.getElementById('updateInterval'),
    statusText: document.getElementById('statusText'),
    lastUpdate: document.getElementById('lastUpdate'),
    headerBusInfo: document.getElementById('headerBusInfo'),
    // New elements for info cards
    currentRoadName: document.getElementById('currentRoadName'),
    currentLinkId: document.getElementById('currentLinkId'),
    currentSpeedBand: document.getElementById('currentSpeedBand'),
    nextRoadName: document.getElementById('nextRoadName'),
    nextLinkId: document.getElementById('nextLinkId'),
    nextSpeedBand: document.getElementById('nextSpeedBand'),
    inboundCount: document.getElementById('inboundCount'),
    outboundCount: document.getElementById('outboundCount'),
    inboundLinksList: document.getElementById('inboundLinksList'),
    outboundLinksList: document.getElementById('outboundLinksList'),
    // Map control buttons
    toggleRouteBtn: document.getElementById('toggleRouteBtn'),
    toggleInboundBtn: document.getElementById('toggleInboundBtn'),
    toggleOutboundBtn: document.getElementById('toggleOutboundBtn'),
    autoFollowBtn: document.getElementById('autoFollowBtn'),
    // Demo mode controls
    demoModeToggle: document.getElementById('demoModeToggle'),
    simulationControls: document.getElementById('simulationControls'),
    manualControls: document.getElementById('manualControls'),
    demoScenario: document.getElementById('demoScenario'),
    simStartBtn: document.getElementById('simStartBtn'),
    simPauseBtn: document.getElementById('simPauseBtn'),
    simResetBtn: document.getElementById('simResetBtn'),
    simSpeed: document.getElementById('simSpeed'),
    simProgressText: document.getElementById('simProgressText'),
    simProgressPercent: document.getElementById('simProgressPercent'),
    simProgressBar: document.getElementById('simProgressBar'),
    // Driver view expand/collapse
    driverViewToggleBtn: document.getElementById('driverViewToggleBtn'),
    // Driver view primary display
    advisedSpeed: document.getElementById('advisedSpeed'),
    currentSpeedInline: document.getElementById('currentSpeedInline'),
    predictedSpeedInline: document.getElementById('predictedSpeedInline')
};

// Driver view state
let isDriverMode = false;

function setDriverMode(enabled) {
    isDriverMode = enabled;
    document.body.classList.toggle('driver-mode', enabled);

    if (elements.driverViewToggleBtn) {
        elements.driverViewToggleBtn.setAttribute('aria-pressed', enabled ? 'true' : 'false');
        elements.driverViewToggleBtn.title = enabled ? 'Return to Control Center View' : 'Expand Driver View';

        const icon = elements.driverViewToggleBtn.querySelector('.driver-view-toggle-icon');
        if (icon) icon.textContent = enabled ? '⤡' : '⤢';
    }

    // When returning to control center view, Leaflet needs a size invalidation
    if (!enabled && map) {
        setTimeout(() => {
            try {
                map.invalidateSize(true);
            } catch (e) {
                console.warn('Map invalidateSize failed:', e);
            }
        }, 50);
    }
}

function toggleDriverMode() {
    setDriverMode(!isDriverMode);
}

// Initialize Speech Synthesis
function initSpeechSynthesis() {
    if ('speechSynthesis' in window) {
        speechSynthesis = window.speechSynthesis;
        console.log('Speech synthesis available');
    } else {
        console.warn('Speech synthesis not supported');
    }
}

// Speak text using Web Speech API
function speak(text) {
    if (!elements.voiceEnabled.checked || !speechSynthesis) {
        return;
    }

    speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.9;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;

    // Pause simulation during voiceover in demo mode
    if (isDemoMode && simulationManager && simulationManager.isRunning && !simulationManager.isPaused) {
        // Get current position before pausing to ensure marker stays in place
        const currentPosition = simulationManager.getCurrentPosition();
        
        isWaitingForVoice = true;
        simulationManager.pause();
        
        // Ensure bus marker stays at current position while paused
        if (currentPosition) {
            updateBusMarker(currentPosition.lat, currentPosition.lon);
        }
        
        console.log('Simulation paused for voiceover at:', currentPosition);
    }

    // Resume when voiceover completes
    utterance.onend = () => {
        if (isDemoMode && simulationManager && isWaitingForVoice) {
            isWaitingForVoice = false;
            simulationManager.resume();
            console.log('Simulation resumed after voiceover');
        }
    };

    // Resume on error as well
    utterance.onerror = () => {
        if (isDemoMode && simulationManager && isWaitingForVoice) {
            isWaitingForVoice = false;
            simulationManager.resume();
            console.log('Simulation resumed after voiceover error');
        }
    };

    const voices = speechSynthesis.getVoices();
    const preferredVoice = voices.find(voice => 
        voice.lang.includes('en') && voice.name.includes('Female')
    ) || voices.find(voice => voice.lang.includes('en'));
    
    if (preferredVoice) {
        utterance.voice = preferredVoice;
    }

    speechSynthesis.speak(utterance);
}

// Initialize Leaflet Map
function initMap() {
    // Create map centered on Singapore
    map = L.map('map').setView([1.3521, 103.8198], 12);

    // Add OpenStreetMap tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19
    }).addTo(map);

    // Initialize layer groups
    routePreviewLayer = L.layerGroup().addTo(map);
    routeLayer = L.layerGroup().addTo(map);
    currentLinkLayer = L.layerGroup().addTo(map);
    nextLinksLayer = L.layerGroup().addTo(map);
    inboundLinksLayer = L.layerGroup().addTo(map);
    outboundLinksLayer = L.layerGroup().addTo(map);
    trailLayer = L.layerGroup().addTo(map);

    // Add click handler to map for coordinate selection
    map.on('click', function(e) {
        const lat = e.latlng.lat.toFixed(6);
        const lon = e.latlng.lng.toFixed(6);
        
        // Update input fields
        elements.latitude.value = lat;
        elements.longitude.value = lon;
        
        // Remove old click marker if exists
        if (clickMarker) {
            map.removeLayer(clickMarker);
        }
        
        // Add new click marker
        clickMarker = L.marker([e.latlng.lat, e.latlng.lng], {
            icon: L.divIcon({
                className: 'click-marker',
                html: '<div class="click-marker-icon">📍</div>',
                iconSize: [30, 30],
                iconAnchor: [15, 30]
            })
        }).addTo(map);
        
        clickMarker.bindPopup(`
            <b>Selected Location</b><br>
            Lat: ${lat}<br>
            Lon: ${lon}
        `).openPopup();
        
        console.log(`Map clicked: ${lat}, ${lon}`);
    });

    console.log('Map initialized');
}

// Get speedband color
function getSpeedbandColor(speedband) {
    const colors = {
        8: '#006400', // Dark Green - Very Fast (70+ km/h)
        7: '#228B22', // Green - Fast (60-69 km/h)
        6: '#32CD32', // Light Green - Faster (50-59 km/h)
        5: '#9ACD32', // Yellow-Green - Fast (40-49 km/h)
        4: '#FFFF00', // Yellow - Medium (30-39 km/h)
        3: '#FFA500', // Orange - Moderate (20-29 km/h)
        2: '#FF4500', // Red-Orange - Slow (10-19 km/h)
        1: '#FF0000'  // Red - Very Slow (0-9 km/h)
    };
    return colors[speedband] || '#808080'; // Gray for unknown
}

// Create popup content for a link
function createLinkPopup(link) {
    const speedband = link.SpeedBand || 'N/A';
    const minSpeed = link.MinimumSpeed || 'N/A';
    const maxSpeed = link.MaximumSpeed || 'N/A';
    
    return `
        <div style="font-family: Arial, sans-serif;">
            <b>Link ${link.LinkID}</b><br>
            <b>Road:</b> ${link.RoadName || 'N/A'}<br>
            <b>SpeedBand:</b> ${speedband}<br>
            <b>Speed:</b> ${minSpeed}-${maxSpeed} km/h<br>
            <b>Order:</b> ${link.order || 'N/A'}
        </div>
    `;
}

// Draw a link on the map
function drawLink(link, layer, options = {}) {
    const {
        weight = 5,
        opacity = 0.8,
        dashArray = null,
        color = null
    } = options;

    const linkColor = color || getSpeedbandColor(link.SpeedBand);
    
    const polyline = L.polyline([
        [link.StartLat, link.StartLon],
        [link.EndLat, link.EndLon]
    ], {
        color: linkColor,
        weight: weight,
        opacity: opacity,
        dashArray: dashArray
    });

    polyline.bindPopup(createLinkPopup(link));
    polyline.addTo(layer);
}

// Draw entire route
function drawRoute(routeGeometry) {
    routeLayer.clearLayers();
    
    if (!showRoute) return;

    routeGeometry.forEach(link => {
        drawLink(link, routeLayer, {
            weight: 3,
            opacity: 0.3,
            color: '#999999'
        });
    });
}

// Draw current link
function drawCurrentLink(currentLink) {
    currentLinkLayer.clearLayers();
    
    if (!currentLink) return;

    drawLink(currentLink, currentLinkLayer, {
        weight: 8,
        opacity: 1.0
    });
}

// Draw next links
function drawNextLinks(nextLinks) {
    nextLinksLayer.clearLayers();
    
    if (!nextLinks || nextLinks.length === 0) return;

    nextLinks.forEach((link, index) => {
        // Use predicted speedband if available, otherwise use actual
        drawLink(link, nextLinksLayer, {
            weight: 6,
            opacity: 0.9
        });
    });
}

// Draw inbound links
function drawInboundLinks(inboundLinks) {
    inboundLinksLayer.clearLayers();
    
    if (!showInbound || !inboundLinks || inboundLinks.length === 0) return;

    inboundLinks.forEach(link => {
        drawLink(link, inboundLinksLayer, {
            weight: 4,
            opacity: 0.6,
            dashArray: '10, 5'
        });
    });
}

// Draw outbound links
function drawOutboundLinks(outboundLinks) {
    outboundLinksLayer.clearLayers();
    
    if (!showOutbound || !outboundLinks || outboundLinks.length === 0) return;

    outboundLinks.forEach(link => {
        drawLink(link, outboundLinksLayer, {
            weight: 4,
            opacity: 0.6,
            dashArray: '5, 10'
        });
    });
}

// Update or create bus marker
function updateBusMarker(lat, lon) {
    const busIcon = L.divIcon({
        className: 'bus-marker',
        html: '<div class="bus-icon">🚌</div>',
        iconSize: [40, 40],
        iconAnchor: [20, 20]
    });

    if (busMarker) {
        busMarker.setLatLng([lat, lon]);
    } else {
        busMarker = L.marker([lat, lon], { icon: busIcon }).addTo(map);
        busMarker.bindPopup('Current Bus Location');
    }

    // Auto-follow bus if enabled (smooth panning in demo mode)
    if (autoFollow) {
        if (isDemoMode) {
            // Use panTo for smooth following in demo mode
            map.panTo([lat, lon], {
                animate: true,
                duration: 0.5,
                noMoveStart: true
            });
        } else {
            // Instant view update in manual mode
            map.setView([lat, lon], map.getZoom());
        }
    }
}

// Display route preview
function displayRoutePreview(routeData) {
    if (!routeData || !routeData.ordered_links) {
        console.error('No route data to display');
        return;
    }

    // Clear existing route preview
    routePreviewLayer.clearLayers();

    const orderedLinks = routeData.ordered_links;
    console.log(`Displaying route preview with ${orderedLinks.length} links`);

    // Draw all route links in blue
    const allCoordinates = [];
    orderedLinks.forEach((link, index) => {
        const polyline = L.polyline([
            [link.StartLat, link.StartLon],
            [link.EndLat, link.EndLon]
        ], {
            color: '#0066CC',
            weight: 4,
            opacity: 0.5
        });

        // Add popup with link info
        polyline.bindPopup(`
            <div style="font-family: Arial, sans-serif;">
                <b>Link ${link.LinkID}</b><br>
                <b>Road:</b> ${link.RoadName || 'N/A'}<br>
                <b>Order:</b> ${index} / ${orderedLinks.length}
            </div>
        `);

        polyline.addTo(routePreviewLayer);

        // Collect coordinates for bounds
        allCoordinates.push([link.StartLat, link.StartLon]);
        allCoordinates.push([link.EndLat, link.EndLon]);
    });

    // Add start marker (green)
    if (orderedLinks.length > 0) {
        const firstLink = orderedLinks[0];
        const startMarker = L.circleMarker([firstLink.StartLat, firstLink.StartLon], {
            radius: 8,
            fillColor: '#00CC00',
            color: '#006600',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8
        });
        startMarker.bindPopup('<b>Route Start</b>');
        startMarker.addTo(routePreviewLayer);
    }

    // Add end marker (red)
    if (orderedLinks.length > 0) {
        const lastLink = orderedLinks[orderedLinks.length - 1];
        const endMarker = L.circleMarker([lastLink.EndLat, lastLink.EndLon], {
            radius: 8,
            fillColor: '#CC0000',
            color: '#660000',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8
        });
        endMarker.bindPopup('<b>Route End</b>');
        endMarker.addTo(routePreviewLayer);
    }

    // Fit map bounds to show entire route
    if (allCoordinates.length > 0) {
        const bounds = L.latLngBounds(allCoordinates);
        map.fitBounds(bounds, { padding: [50, 50] });
    }

    console.log('Route preview displayed');
}

// Update all map layers
function updateMapLayers(mapData) {
    currentMapData = mapData;

    // Draw route
    if (mapData.route_geometry) {
        drawRoute(mapData.route_geometry);
    }

    // Draw current link
    if (mapData.current_link) {
        drawCurrentLink(mapData.current_link);
    }

    // Draw next links
    if (mapData.next_links) {
        drawNextLinks(mapData.next_links);
    }

    // Draw inbound links
    if (mapData.inbound_links) {
        drawInboundLinks(mapData.inbound_links);
    }

    // Draw outbound links
    if (mapData.outbound_links) {
        drawOutboundLinks(mapData.outbound_links);
    }

    // Update bus marker
    if (mapData.bus_location) {
        updateBusMarker(mapData.bus_location.lat, mapData.bus_location.lon);
    }
}

// Update info cards
function updateInfoCards(recommendation) {
    if (!recommendation) return;

    // Update current link info
    if (recommendation.current_link) {
        const currentLink = recommendation.current_link;
        elements.currentRoadName.textContent = currentLink.RoadName || '--';
        elements.currentLinkId.textContent = currentLink.LinkID || '--';
        
        const currentSpeedBand = currentLink.SpeedBand || 0;
        elements.currentSpeedBand.textContent = currentSpeedBand;
        elements.currentSpeedBand.className = `speedband-badge speedband-${currentSpeedBand}`;
    }

    // Update next link info
    if (recommendation.next_link) {
        const nextLink = recommendation.next_link;
        elements.nextRoadName.textContent = nextLink.RoadName || '--';
        elements.nextLinkId.textContent = nextLink.LinkID || '--';
        
        const nextSpeedBand = nextLink.SpeedBand || 0;
        elements.nextSpeedBand.textContent = nextSpeedBand;
        elements.nextSpeedBand.className = `speedband-badge speedband-${nextSpeedBand}`;
    }

    // Update inbound links
    if (recommendation.inbound_links) {
        elements.inboundCount.textContent = recommendation.inbound_links.length;
        
        if (recommendation.inbound_links.length > 0) {
            elements.inboundLinksList.innerHTML = recommendation.inbound_links.map(link => {
                const speedBand = link.SpeedBand || 0;
                return `
                    <div class="link-item">
                        <span class="link-item-name">${link.RoadName || 'Unknown'}</span>
                        <span class="speedband-badge speedband-${speedBand}">${speedBand}</span>
                    </div>
                `;
            }).join('');
        } else {
            elements.inboundLinksList.textContent = 'None';
        }
    }

    // Update outbound links
    if (recommendation.outbound_links) {
        elements.outboundCount.textContent = recommendation.outbound_links.length;
        
        if (recommendation.outbound_links.length > 0) {
            elements.outboundLinksList.innerHTML = recommendation.outbound_links.map(link => {
                const speedBand = link.SpeedBand || 0;
                return `
                    <div class="link-item">
                        <span class="link-item-name">${link.RoadName || 'Unknown'}</span>
                        <span class="speedband-badge speedband-${speedBand}">${speedBand}</span>
                    </div>
                `;
            }).join('');
        } else {
            elements.outboundLinksList.textContent = 'None';
        }
    }
}

// Get GPS location
function getGPSLocation() {
    if (!navigator.geolocation) {
        alert('GPS is not supported by your browser');
        return;
    }

    elements.statusText.textContent = 'Getting GPS location...';
    elements.getLocationBtn.disabled = true;

    navigator.geolocation.getCurrentPosition(
        (position) => {
            elements.latitude.value = position.coords.latitude.toFixed(6);
            elements.longitude.value = position.coords.longitude.toFixed(6);
            elements.statusText.textContent = 'GPS location obtained';
            elements.getLocationBtn.disabled = false;
        },
        (error) => {
            console.error('GPS error:', error);
            alert('Failed to get GPS location: ' + error.message);
            elements.statusText.textContent = 'GPS error';
            elements.getLocationBtn.disabled = false;
        },
        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        }
    );
}

// Fetch recommendation from API
async function fetchRecommendation() {
    const busNo = elements.busNo.value;
    const direction = elements.direction.value;
    const lat = parseFloat(elements.latitude.value);
    const lon = parseFloat(elements.longitude.value);

    if (!busNo || !direction || isNaN(lat) || isNaN(lon)) {
        elements.statusText.textContent = 'Please fill in all fields';
        return null;
    }

    try {
        const url = `${API_BASE_URL}/coasting_recommendation?bus_no=${busNo}&direction=${direction}&lat=${lat}&lon=${lon}`;
        elements.statusText.textContent = 'Fetching recommendation...';
        
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('API error:', error);
        elements.statusText.textContent = `Error: ${error.message}`;
        return null;
    }
}

// Fetch route geometry for preview
async function fetchRouteGeometry() {
    const busNo = elements.busNo.value;
    const direction = elements.direction.value;

    if (!busNo || !direction) {
        elements.statusText.textContent = 'Please select bus number and direction';
        return null;
    }

    try {
        const url = `${API_BASE_URL}/route_geometry?bus_no=${busNo}&direction=${direction}`;
        elements.statusText.textContent = 'Loading route...';
        
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        elements.statusText.textContent = 'Route loaded';
        return data;
    } catch (error) {
        console.error('Route API error:', error);
        elements.statusText.textContent = `Error loading route: ${error.message}`;
        return null;
    }
}

// Update UI with recommendation
function updateUI(recommendation) {
    if (!recommendation) {
        return;
    }

    // Update action indicator
    const action = recommendation.action;

    // Style action tile by action type (matches driver view reference design)
    if (elements.actionIndicator) {
        elements.actionIndicator.dataset.action = action || '';
    }

    elements.actionIndicator.className = `action-indicator updating`;
    
    setTimeout(() => {
        elements.actionIndicator.classList.remove('updating');
    }, 500);

    // Update action icon and text
    const actionMap = {
        'maintain_speed': { icon: '▶', text: 'Maintain Speed' },
        'coast': { icon: '⏸', text: 'Coast' },
        'speed_up': { icon: '⏩', text: 'Speed Up' },
        'crawl': { icon: '⬇', text: 'Crawl' }
    };

    const actionInfo = actionMap[action] || { icon: '⏸', text: action };
    elements.actionIcon.textContent = actionInfo.icon;
    elements.actionText.textContent = actionInfo.text;

    // Update speeds
    elements.currentSpeed.textContent = recommendation.current_speed.toFixed(0);
    elements.predictedSpeed.textContent = recommendation.predicted_speed.toFixed(0);

    // Driver view primary (big) speed display
    if (elements.advisedSpeed) {
        // Maintain uses current as target; other actions use predicted (upcoming) speed.
        const targetSpeed = action === 'maintain_speed'
            ? recommendation.current_speed
            : recommendation.predicted_speed;
        elements.advisedSpeed.textContent = Number.isFinite(targetSpeed) ? targetSpeed.toFixed(0) : '--';
    }
    if (elements.currentSpeedInline) {
        elements.currentSpeedInline.textContent = recommendation.current_speed.toFixed(0);
    }
    if (elements.predictedSpeedInline) {
        elements.predictedSpeedInline.textContent = recommendation.predicted_speed.toFixed(0);
    }

    // Update reasoning
    elements.reasoning.textContent = recommendation.reasoning;

    // Update status indicators
    if (recommendation.has_rain) {
        elements.rainIndicator.classList.add('active');
    } else {
        elements.rainIndicator.classList.remove('active');
    }

    if (recommendation.has_incident) {
        elements.incidentIndicator.classList.add('active');
    } else {
        elements.incidentIndicator.classList.remove('active');
    }

    // Update info cards
    updateInfoCards(recommendation);

    // Update map layers if we have link data
    if (recommendation.current_link) {
        const lat = parseFloat(elements.latitude.value);
        const lon = parseFloat(elements.longitude.value);
        
        const mapData = {
            route_geometry: [], // We'll need to fetch full route separately
            current_link: recommendation.current_link,
            next_links: recommendation.next_link ? [recommendation.next_link] : [],
            inbound_links: recommendation.inbound_links || [],
            outbound_links: recommendation.outbound_links || [],
            bus_location: { lat, lon }
        };
        
        updateMapLayers(mapData);
    }

    // Voice announcement (only if action changed or in demo mode)
    if (elements.voiceEnabled.checked) {
        if (action !== lastAction || isDemoMode) {
            const voiceText = `${actionInfo.text}. ${recommendation.reasoning}`;
            speak(voiceText);
            lastAction = action;
        }
    }

    // Update status
    elements.statusText.textContent = `Active - ${actionInfo.text}`;
    elements.lastUpdate.textContent = `Last update: ${new Date().toLocaleTimeString()}`;

    // Update header
    const busNo = elements.busNo.value;
    const direction = elements.direction.value;
    elements.headerBusInfo.textContent = `Bus ${busNo} | Direction ${direction}`;
}

// Start polling
function startPolling() {
    const intervalSeconds = parseInt(elements.updateIntervalInput.value) || 5;
    
    // Fetch immediately
    fetchRecommendation().then(updateUI);

    // Then poll at interval
    updateInterval = setInterval(async () => {
        const recommendation = await fetchRecommendation();
        updateUI(recommendation);
    }, intervalSeconds * 1000);

    elements.startBtn.disabled = true;
    elements.stopBtn.disabled = false;
    elements.statusText.textContent = 'Polling started';
}

// Stop polling
function stopPolling() {
    if (updateInterval) {
        clearInterval(updateInterval);
        updateInterval = null;
    }

    if (speechSynthesis) {
        speechSynthesis.cancel();
    }

    // Reset voice waiting flag
    isWaitingForVoice = false;

    elements.startBtn.disabled = false;
    elements.stopBtn.disabled = true;
    elements.statusText.textContent = 'Stopped';
    lastAction = null;
}

// Toggle layer visibility
function toggleLayer(layerType) {
    switch(layerType) {
        case 'route':
            showRoute = !showRoute;
            elements.toggleRouteBtn.classList.toggle('active');
            if (currentMapData) {
                drawRoute(currentMapData.route_geometry || []);
            }
            break;
        case 'inbound':
            showInbound = !showInbound;
            elements.toggleInboundBtn.classList.toggle('active');
            if (currentMapData) {
                drawInboundLinks(currentMapData.inbound_links || []);
            }
            break;
        case 'outbound':
            showOutbound = !showOutbound;
            elements.toggleOutboundBtn.classList.toggle('active');
            if (currentMapData) {
                drawOutboundLinks(currentMapData.outbound_links || []);
            }
            break;
        case 'autofollow':
            autoFollow = !autoFollow;
            elements.autoFollowBtn.classList.toggle('active');
            break;
    }
}

// Load and display route preview
async function loadRoutePreview() {
    const routeData = await fetchRouteGeometry();
    if (routeData) {
        displayRoutePreview(routeData);
    }
}

// ============================================================================
// SIMULATION FUNCTIONS
// ============================================================================

/**
 * Initialize the simulation manager
 */
function initializeSimulation() {
    if (!simulationManager) {
        simulationManager = new SimulationManager();
        
        // Set up callbacks
        simulationManager.onPositionUpdate = handleSimulationPositionUpdate;
        simulationManager.onLinkChange = handleSimulationLinkChange;
        simulationManager.onComplete = handleSimulationComplete;
        
        console.log('Simulation manager initialized');
    }
}

/**
 * Toggle demo mode on/off
 */
function toggleDemoMode() {
    isDemoMode = elements.demoModeToggle.checked;
    
    if (isDemoMode) {
        // Entering demo mode
        console.log('Entering demo mode');
        elements.simulationControls.style.display = 'flex';
        elements.manualControls.style.display = 'none';
        elements.statusText.textContent = 'Demo Mode - Select scenario and start';
        
        // Stop any existing polling
        stopPolling();
        
        // Initialize simulation if not already done
        initializeSimulation();
        
        // Load default scenario
        loadDemoScenario();
        
    } else {
        // Exiting demo mode
        console.log('Exiting demo mode');
        elements.simulationControls.style.display = 'none';
        elements.manualControls.style.display = 'flex';
        elements.statusText.textContent = 'Manual Mode - Ready';
        
        // Stop simulation
        if (simulationManager) {
            simulationManager.stop();
        }
        
        // Clear simulation visuals
        clearSimulationVisuals();
    }
}

/**
 * Load and start a demo scenario
 */
async function loadDemoScenario() {
    const scenario = elements.demoScenario.value;
    const [busNo, direction] = scenario.split('-').map(Number);
    
    elements.statusText.textContent = `Loading Bus ${busNo} Direction ${direction}...`;
    
    try {
        // Fetch both route geometry (for links) and OSRM route geometry (for continuous path)
        const [linksResponse, osrmResponse] = await Promise.all([
            fetch(`${API_BASE_URL}/route_geometry?bus_no=${busNo}&direction=${direction}`),
            fetch(`${API_BASE_URL}/osrm_route_geometry?bus_no=${busNo}&direction=${direction}`)
        ]);
        
        if (!linksResponse.ok) {
            throw new Error(`HTTP error! status: ${linksResponse.status}`);
        }
        
        if (!osrmResponse.ok) {
            console.warn('OSRM route geometry not available, falling back to links only');
        }
        
        const linksData = await linksResponse.json();
        const osrmData = osrmResponse.ok ? await osrmResponse.json() : null;
        
        simulationRouteData = linksData;
        
        // Initialize simulation with ordered links and OSRM route path
        if (simulationManager.initialize(linksData.ordered_links, osrmData ? osrmData.route_path : null)) {
            const statusMsg = osrmData 
                ? `Route loaded: ${linksData.total_links} links, ${osrmData.total_points} OSRM points. Click Start to begin.`
                : `Route loaded: ${linksData.total_links} links. Click Start to begin.`;
            elements.statusText.textContent = statusMsg;
            
            // Update header
            elements.headerBusInfo.textContent = `Bus ${busNo} | Direction ${direction}`;
            
            // Display route on map
            displayRoutePreview(linksData);
            
            // If OSRM data is available, also draw the continuous route
            if (osrmData && osrmData.route_path && osrmData.route_path.length > 0) {
                drawOSRMRoute(osrmData.route_path);
            }
            
            // Zoom to starting position and enable auto-follow
            if (osrmData && osrmData.route_path && osrmData.route_path.length > 0) {
                // Use OSRM route start point
                const startPoint = osrmData.route_path[0];
                map.setView([startPoint[0], startPoint[1]], 15);
            } else if (linksData.ordered_links && linksData.ordered_links.length > 0) {
                // Fallback to first link
                const firstLink = linksData.ordered_links[0];
                const startLat = parseFloat(firstLink.StartLat);
                const startLon = parseFloat(firstLink.StartLon);
                map.setView([startLat, startLon], 15);
            }
            
            // Ensure auto-follow is enabled for simulation
            autoFollow = true;
            elements.autoFollowBtn.classList.add('active');
            
            // Enable start button
            elements.simStartBtn.disabled = false;
            elements.simResetBtn.disabled = false;
            
            // Update progress display
            updateSimulationProgress();
        }
    } catch (error) {
        console.error('Error loading demo scenario:', error);
        elements.statusText.textContent = `Error loading route: ${error.message}`;
    }
}

/**
 * Draw OSRM continuous route on the map
 */
function drawOSRMRoute(routePath) {
    if (!routePath || routePath.length < 2) return;
    
    // Convert [[lat, lon], ...] to Leaflet format
    const latlngs = routePath.map(point => [point[0], point[1]]);
    
    // Draw continuous route line
    const osrmRouteLine = L.polyline(latlngs, {
        color: '#0066FF',
        weight: 3,
        opacity: 0.6,
        dashArray: '10, 5'
    });
    
    osrmRouteLine.addTo(routePreviewLayer);
    console.log(`Drew OSRM route with ${routePath.length} points`);
}

/**
 * Start the simulation
 */
function startSimulation() {
    if (!simulationManager || !simulationRouteData) {
        console.error('Cannot start simulation: not initialized');
        return;
    }
    
    // Reset API call timer to trigger immediate call
    lastSimulationApiCall = 0;
    
    // Ensure auto-follow is enabled
    autoFollow = true;
    elements.autoFollowBtn.classList.add('active');
    
    // Get starting position and zoom to it
    const position = simulationManager.getCurrentPosition();
    if (position) {
        map.setView([position.lat, position.lon], 16, {
            animate: true,
            duration: 1
        });
    }
    
    simulationManager.start();
    
    elements.simStartBtn.disabled = true;
    elements.simPauseBtn.disabled = false;
    elements.simPauseBtn.innerHTML = '<span class="btn-icon">⏸</span> Pause';
    elements.statusText.textContent = 'Simulation running...';
}

/**
 * Pause/resume the simulation
 */
function toggleSimulationPause() {
    if (!simulationManager) return;
    
    const state = simulationManager.getState();
    
    if (state.isPaused) {
        simulationManager.resume();
        elements.simPauseBtn.innerHTML = '<span class="btn-icon">⏸</span> Pause';
        elements.statusText.textContent = 'Simulation running...';
    } else {
        simulationManager.pause();
        elements.simPauseBtn.innerHTML = '<span class="btn-icon">▶</span> Resume';
        elements.statusText.textContent = 'Simulation paused';
    }
}

/**
 * Reset the simulation
 */
function resetSimulation() {
    if (!simulationManager) return;
    
    simulationManager.reset();
    
    elements.simStartBtn.disabled = false;
    elements.simPauseBtn.disabled = true;
    elements.simPauseBtn.innerHTML = '<span class="btn-icon">⏸</span> Pause';
    elements.statusText.textContent = 'Simulation reset. Click Start to begin.';
    
    // Clear trail
    if (trailLayer) {
        trailLayer.clearLayers();
    }
    
    // Reset API call timer and link tracking
    lastSimulationApiCall = 0;
    lastLinkIndexForRecommendation = -1;
    
    // Reset voice action state
    lastAction = null;
    isWaitingForVoice = false;
    
    // Cancel any ongoing speech
    if (speechSynthesis) {
        speechSynthesis.cancel();
    }
    
    // Zoom back to start of route
    if (simulationRouteData && simulationRouteData.ordered_links && simulationRouteData.ordered_links.length > 0) {
        const firstLink = simulationRouteData.ordered_links[0];
        const startLat = parseFloat(firstLink.StartLat);
        const startLon = parseFloat(firstLink.StartLon);
        map.setView([startLat, startLon], 15);
    }
    
    // Update progress
    updateSimulationProgress();
}

/**
 * Change simulation speed
 */
function changeSimulationSpeed() {
    if (!simulationManager) return;
    
    const speed = parseFloat(elements.simSpeed.value);
    simulationManager.setSpeed(speed);
    
    console.log(`Simulation speed changed to ${speed}x`);
}

/**
 * Handle position updates from simulation
 */
function handleSimulationPositionUpdate(position) {
    // Update bus marker position smoothly
    updateBusMarker(position.lat, position.lon);
    
    // Update progress display
    updateSimulationProgress();
    
    // Check if we've entered a new link (priority trigger)
    const currentLinkIndex = position.linkIndex !== undefined ? position.linkIndex : -1;
    if (currentLinkIndex >= 0 && currentLinkIndex !== lastLinkIndexForRecommendation) {
        // New link detected - trigger recommendation immediately
        lastLinkIndexForRecommendation = currentLinkIndex;
        lastSimulationApiCall = performance.now();
        fetchSimulationRecommendation(position.lat, position.lon);
        console.log(`Triggered recommendation for new link: ${currentLinkIndex}`);
        return;
    }
    
    // Fallback: periodic recommendation check (every 3 seconds)
    const now = performance.now();
    if (now - lastSimulationApiCall >= SIMULATION_API_INTERVAL) {
        lastSimulationApiCall = now;
        fetchSimulationRecommendation(position.lat, position.lon);
    }
}

/**
 * Handle link changes in simulation
 */
function handleSimulationLinkChange(linkIndex, link) {
    console.log(`Simulation moved to link ${linkIndex}: ${link.RoadName || link.LinkID}`);
    
    // Draw trail for the previous link
    if (linkIndex > 0 && simulationManager.orderedLinks) {
        const prevLink = simulationManager.orderedLinks[linkIndex - 1];
        if (prevLink) {
            drawTrailSegment(prevLink);
        }
    }
    
    // Trigger recommendation when entering a new link
    // Get current position to fetch recommendation
    const position = simulationManager.getCurrentPosition();
    if (position) {
        lastLinkIndexForRecommendation = linkIndex;
        lastSimulationApiCall = performance.now();
        fetchSimulationRecommendation(position.lat, position.lon);
        console.log(`Triggered recommendation on link change: ${linkIndex}`);
    }
}

/**
 * Handle simulation completion
 */
function handleSimulationComplete() {
    elements.statusText.textContent = 'Simulation complete!';
    elements.simStartBtn.disabled = true;
    elements.simPauseBtn.disabled = true;
    
    console.log('Simulation finished');
    
    // Optionally, speak completion message
    if (elements.voiceEnabled.checked) {
        speak('Simulation complete. Route finished.');
    }
}

/**
 * Fetch recommendation for current simulation position
 */
async function fetchSimulationRecommendation(lat, lon) {
    const scenario = elements.demoScenario.value;
    const [busNo, direction] = scenario.split('-').map(Number);
    
    try {
        const url = `${API_BASE_URL}/coasting_recommendation?bus_no=${busNo}&direction=${direction}&lat=${lat}&lon=${lon}`;
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        updateUI(data);
    } catch (error) {
        console.error('Error fetching simulation recommendation:', error);
    }
}

/**
 * Update simulation progress display
 */
function updateSimulationProgress() {
    if (!simulationManager) return;
    
    const state = simulationManager.getState();
    const currentLink = state.currentLinkIndex + 1;
    const totalLinks = state.totalLinks;
    const progress = (currentLink / totalLinks) * 100;
    
    elements.simProgressText.textContent = `Link ${currentLink} / ${totalLinks}`;
    elements.simProgressPercent.textContent = `${Math.round(progress)}%`;
    elements.simProgressBar.style.width = `${progress}%`;
}

/**
 * Draw trail segment for a visited link
 */
function drawTrailSegment(link) {
    if (!trailLayer) return;
    
    const polyline = L.polyline([
        [link.StartLat, link.StartLon],
        [link.EndLat, link.EndLon]
    ], {
        color: '#4CAF50',
        weight: 4,
        opacity: 0.5,
        dashArray: '5, 10'
    });
    
    polyline.addTo(trailLayer);
}

/**
 * Clear all simulation visuals
 */
function clearSimulationVisuals() {
    if (trailLayer) {
        trailLayer.clearLayers();
    }
    if (routePreviewLayer) {
        routePreviewLayer.clearLayers();
    }
    if (busMarker) {
        map.removeLayer(busMarker);
        busMarker = null;
    }
}

// Event Listeners
elements.loadRouteBtn.addEventListener('click', loadRoutePreview);
elements.getLocationBtn.addEventListener('click', getGPSLocation);

elements.startBtn.addEventListener('click', () => {
    if (!elements.latitude.value || !elements.longitude.value) {
        alert('Please enter GPS coordinates or use the "Use GPS" button');
        return;
    }
    startPolling();
});

elements.stopBtn.addEventListener('click', stopPolling);

elements.updateIntervalInput.addEventListener('change', () => {
    if (updateInterval) {
        stopPolling();
        startPolling();
    }
});

// Map control buttons
elements.toggleRouteBtn.addEventListener('click', () => toggleLayer('route'));
elements.toggleInboundBtn.addEventListener('click', () => toggleLayer('inbound'));
elements.toggleOutboundBtn.addEventListener('click', () => toggleLayer('outbound'));
elements.autoFollowBtn.addEventListener('click', () => toggleLayer('autofollow'));

// Bus number and direction change listeners
elements.busNo.addEventListener('change', loadRoutePreview);
elements.direction.addEventListener('change', loadRoutePreview);

// Demo mode toggle
elements.demoModeToggle.addEventListener('change', toggleDemoMode);

// Demo scenario change
elements.demoScenario.addEventListener('change', loadDemoScenario);

// Simulation control buttons
elements.simStartBtn.addEventListener('click', startSimulation);
elements.simPauseBtn.addEventListener('click', toggleSimulationPause);
elements.simResetBtn.addEventListener('click', resetSimulation);
elements.simSpeed.addEventListener('change', changeSimulationSpeed);

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initSpeechSynthesis();
    initMap();

    // Driver view expand/collapse
    if (elements.driverViewToggleBtn) {
        elements.driverViewToggleBtn.addEventListener('click', toggleDriverMode);
    }
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && isDriverMode) {
            setDriverMode(false);
        }
    });
    
    // Load voices when available
    if (speechSynthesis) {
        speechSynthesis.onvoiceschanged = () => {
            console.log('Voices loaded');
        };
    }

    // Set default coordinates (Singapore)
    if (!elements.latitude.value) {
        elements.latitude.value = '1.3521';
    }
    if (!elements.longitude.value) {
        elements.longitude.value = '103.8198';
    }

    // Auto-load route preview for default bus
    setTimeout(() => {
        loadRoutePreview();
    }, 500);

    // Initialize simulation manager
    initializeSimulation();
    
    // Load saved simulation speed preference
    const savedSpeed = localStorage.getItem('simSpeed');
    if (savedSpeed) {
        elements.simSpeed.value = savedSpeed;
    }
    
    // Save speed preference when changed
    elements.simSpeed.addEventListener('change', () => {
        localStorage.setItem('simSpeed', elements.simSpeed.value);
    });

    console.log('Predictive Coasting Interface with Map and Simulation initialized');
});
