# Predictive Coasting System for Buses

A predictive coasting system that advises bus drivers when to "Coast" or "Maintain Speed" based on predicted traffic conditions ahead, reducing unnecessary braking and fuel waste.

## Overview

This system combines:
- Real-time traffic speed data (LTA DataMall)
- Bus route mapping and GPS tracking
- Weather data (NEA Rainfall API)
- Traffic incident data
- Machine learning predictions (XGBoost model)
- Driver-friendly interface with voice guidance

## Features

- **Real-time Traffic Prediction**: Uses ML model to predict traffic speeds ahead
- **Coasting Recommendations**: Provides actionable advice (Maintain Speed, Coast, Speed Up, Crawl)
- **Driver Interface**: Web-based interface with color-coded visual cues and voice guidance
- **Multi-factor Analysis**: Considers current speed, predicted speed, rainfall, and incidents
- **🆕 Interactive Demo Mode**: Simulate bus movement along route with real-time recommendations

## Setup

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Create a `.env` file** in the project root with your LTA DataMall credentials:

   ```
   LTA_DATAMALL=your_account_key_here
   ```

   Replace `your_account_key_here` with your actual AccountKey from LTA DataMall.

3. **Start the backend server:**

   ```bash
   python backend/main.py
   ```

   The API will be available at `http://localhost:8000`

4. **Open the frontend interface:**

   - Open `frontend/index.html` in a web browser
   - Enter bus number, direction, and GPS coordinates
   - Click "Start" to begin receiving recommendations

## Quick Start

### Backend API

Start the FastAPI server:
```bash
python backend/main.py
```

The API provides two main endpoints:
- `/realtime_stats` - Get real-time traffic statistics
- `/coasting_recommendation` - Get coasting recommendation for driver

### Frontend Interface

#### Manual Mode (Live GPS)
1. Open `frontend/index.html` in a web browser
2. Enter:
   - Bus number (e.g., 147)
   - Direction (1 or 2)
   - GPS coordinates (or click "Use GPS" if available)
3. Click "Start" to begin polling for recommendations
4. The interface will display:
   - Large color-coded action indicator
   - Current and predicted speeds
   - Reasoning for the recommendation
   - Voice guidance (if enabled)

#### 🆕 Demo Mode (Simulation)
Perfect for hackathon demos and testing!

1. Open `frontend/index.html` in a web browser
2. **Toggle "Demo Mode" ON** at the bottom of the screen
3. Select a demo scenario (e.g., "Bus 147 Direction 1")
4. Click **"Start"** to begin the simulation
5. Watch as the bus automatically moves along the route with:
   - Smooth animated movement on map
   - Real-time coasting recommendations
   - Visual trail showing path traveled
   - Adjustable speed (0.5x to 10x)
   - Progress tracking (current link / total links)

**Demo Mode Features:**
- ✅ No GPS required - fully automated movement
- ✅ Multiple bus routes available (147, 190, 960)
- ✅ Speed control for quick or detailed demos
- ✅ Pause/Resume/Reset controls
- ✅ Visual trail showing route coverage
- ✅ Perfect for presentations and testing

**Quick Demo:** See [DEMO_QUICKSTART.md](DEMO_QUICKSTART.md) for a 30-second setup guide!

### Running Tests

```bash
pytest tests/test_recommendation_service.py -v
```

### Running Demo

**Option 1: Interactive Frontend Simulation (Recommended)**
1. Start backend: `python backend/main.py`
2. Open `frontend/index.html` in browser
3. Enable "Demo Mode" toggle
4. Click "Start" to watch automated bus simulation

See [DEMO_QUICKSTART.md](DEMO_QUICKSTART.md) for detailed instructions.

**Option 2: Command-line Demo**
```bash
python demo/demo_coasting.py
```

Make sure the backend server is running before executing the demo.

## Scripts

### 1. Test Script (`test_traffic_speed_band.py`)

Quick test to verify API connectivity and view sample data.

### 2. Data Collection (`collect_traffic_data.py`)

Collects traffic speed band data every 2 minutes for 2 hours and saves to `traffic_speed_data.json`.

```bash
python collect_traffic_data.py
```

The script will:

- Call the API every 2 minutes for 2 hours (60 total calls)
- Save data incrementally to `traffic_speed_data.json`
- Display progress and statistics

### 3. Visualization (`visualize_traffic_data.py`)

Creates visualizations showing speed changes over time for the first 10 LinkIDs.

```bash
python visualize_traffic_data.py
```

This will generate:

- `traffic_speed_individual.png`: Separate subplot for each LinkID showing speed over time with min/max ranges
- `traffic_speed_combined.png`: Single plot with all LinkIDs overlaid
- Summary statistics printed to console

## Environment Variables

The `.env` file should contain:

- `LTA_DATAMALL`: Your LTA DataMall AccountKey (required for API authentication)

## API Information

- **API Endpoint**: `https://datamall2.mytransport.sg/ltaodataservice/v4/TrafficSpeedBands`
- **Update Frequency**: 5 minutes
- **Documentation**: [LTA DataMall API User Guide](https://datamall.lta.gov.sg/content/dam/datamall/datasets/LTA_DataMall_API_User_Guide.pdf)

## Project Structure

```
SBSHack2026/
├── backend/              # FastAPI backend
│   ├── main.py          # API endpoints
│   └── services/        # Service modules
│       ├── route_service.py
│       ├── link_service.py
│       ├── speed_service.py
│       ├── rainfall_service.py
│       ├── incident_service.py
│       ├── predictor_service.py
│       └── recommendation_service.py
├── frontend/             # Web interface
│   ├── index.html
│   └── static/
│       ├── style.css
│       └── app.js
├── training_data/       # ML model training
│   ├── train_speedband_model.py
│   └── models/
│       └── speedband_model.joblib
├── tests/               # Unit tests
│   └── test_recommendation_service.py
└── demo/                # Demo scripts
    └── demo_coasting.py
```

## API Endpoints

### GET `/coasting_recommendation`

Get coasting recommendation for a bus at a given location.

**Parameters:**
- `bus_no` (int): Bus service number
- `direction` (int): Direction (1 or 2)
- `lat` (float): Current latitude
- `lon` (float): Current longitude

**Response:**
```json
{
  "action": "coast",
  "current_speed": 65.0,
  "predicted_speed": 25.0,
  "reasoning": "Current link is fast (65 km/h) but next link is slow (25 km/h). Start coasting to avoid braking.",
  "urgency": "medium",
  "color_cue": "yellow",
  "has_rain": false,
  "has_incident": false
}
```

## Recommendation Logic

The system implements the following rules:

1. **Maintain Speed**: Current + next link are fast
2. **Speed Up**: Current is fast, next is slowing (if can pass before slowdown)
3. **Coast**: Current is fast, next is slow (earlier if raining)
4. **Crawl**: Both links are slow

## Response Attributes

The API returns traffic speed band data with the following attributes:

- `LinkID`: Unique ID for the road stretch
- `RoadName`: Name of the road
- `RoadCategory`: Road category (1=Expressways, 2=Major Arterial, 3=Arterial, 4=Minor Arterial, 5=Small Roads, 6=Slip Roads, 8=Short Tunnels)
- `SpeedBand`: Speed band (1-8, representing speed ranges from 0-9 km/h to 70+ km/h)
- `MinimumSpeed`: Minimum speed in km/h
- `MaximumSpeed`: Maximum speed in km/h
- `StartLon`, `StartLat`: Longitude and latitude for start point
- `EndLon`, `EndLat`: Longitude and latitude for end point
