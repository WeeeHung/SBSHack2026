// Configuration
const API_BASE_URL = 'http://localhost:8000';
let updateInterval = null;
let lastAction = null;
let speechSynthesis = null;

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
    getLocationBtn: document.getElementById('getLocationBtn'),
    startBtn: document.getElementById('startBtn'),
    stopBtn: document.getElementById('stopBtn'),
    voiceEnabled: document.getElementById('voiceEnabled'),
    updateInterval: document.getElementById('updateInterval'),
    statusText: document.getElementById('statusText'),
    lastUpdate: document.getElementById('lastUpdate')
};

// Initialize Speech Synthesis
function initSpeechSynthesis() {
    if ('speechSynthesis' in window) {
        speechSynthesis = window.speechSynthesis;
        // Get available voices
        const voices = speechSynthesis.getVoices();
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

    // Cancel any ongoing speech
    speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.9; // Slightly slower for clarity
    utterance.pitch = 1.0;
    utterance.volume = 1.0;

    // Try to use a more natural voice
    const voices = speechSynthesis.getVoices();
    const preferredVoice = voices.find(voice => 
        voice.lang.includes('en') && voice.name.includes('Female')
    ) || voices.find(voice => voice.lang.includes('en'));
    
    if (preferredVoice) {
        utterance.voice = preferredVoice;
    }

    speechSynthesis.speak(utterance);
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

    // Validate inputs
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

// Update UI with recommendation
function updateUI(recommendation) {
    if (!recommendation) {
        return;
    }

    // Update action indicator
    const action = recommendation.action;
    const colorCue = recommendation.color_cue;
    
    elements.actionIndicator.className = `action-indicator ${colorCue} updating`;
    
    // Remove updating class after animation
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

    // Voice announcement (only if action changed)
    if (action !== lastAction && elements.voiceEnabled.checked) {
        const voiceText = `${actionInfo.text}. ${recommendation.reasoning}`;
        speak(voiceText);
        lastAction = action;
    }

    // Update status
    elements.statusText.textContent = `Active - ${actionInfo.text}`;
    elements.lastUpdate.textContent = `Last update: ${new Date().toLocaleTimeString()}`;
}

// Start polling
function startPolling() {
    const intervalSeconds = parseInt(elements.updateInterval.value) || 5;
    
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

// Event Listeners
elements.getLocationBtn.addEventListener('click', getGPSLocation);

elements.startBtn.addEventListener('click', () => {
    if (!elements.latitude.value || !elements.longitude.value) {
        alert('Please enter GPS coordinates or use the "Use GPS" button');
        return;
    }
    startPolling();
});

elements.stopBtn.addEventListener('click', stopPolling);

// Update interval when changed
elements.updateInterval.addEventListener('change', () => {
    if (updateInterval) {
        stopPolling();
        startPolling();
    }
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initSpeechSynthesis();
    
    // Load voices when available (some browsers load asynchronously)
    if (speechSynthesis) {
        speechSynthesis.onvoiceschanged = () => {
            console.log('Voices loaded');
        };
    }

    // Set default coordinates (Singapore example)
    if (!elements.latitude.value) {
        elements.latitude.value = '1.3521';
    }
    if (!elements.longitude.value) {
        elements.longitude.value = '103.8198';
    }

    console.log('Predictive Coasting Interface initialized');
});
