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

// Layer visibility state
let showRoute = true;
let showInbound = true;
let showOutbound = true;
let autoFollow = true;

// Current data
let currentMapData = null;

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
    autoFollowBtn: document.getElementById('autoFollowBtn')
};

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

    // Auto-follow bus if enabled
    if (autoFollow) {
        map.setView([lat, lon], map.getZoom());
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
    const colorCue = recommendation.color_cue;
    
    elements.actionIndicator.className = `action-indicator ${colorCue} updating`;
    
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

    // Voice announcement (only if action changed)
    if (action !== lastAction && elements.voiceEnabled.checked) {
        const voiceText = `${actionInfo.text}. ${recommendation.reasoning}`;
        speak(voiceText);
        lastAction = action;
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

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initSpeechSynthesis();
    initMap();
    
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

    console.log('Predictive Coasting Interface with Map initialized');
});
