"""
Configuration constants for the backend API.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Radius for rainfall/incident checking (configurable constant)
RAINFALL_RADIUS_METERS = 50

# Buffer for finding links along route
ROUTE_BUFFER_METERS = 5

# Number of future links to analyze (default: 3)
NUM_FUTURE_LINKS = 3

# DataMall API page size
DATAMALL_PAGE_SIZE = 500

# File paths
LINKS_JSON_PATH = PROJECT_ROOT / "speed_bands" / "data" / "links.json"
BUS_ROUTE_OUTPUT_DIR = PROJECT_ROOT / "bus_route" / "output"

# API Endpoints
DATAMALL_BUS_ROUTES = "https://datamall2.mytransport.sg/ltaodataservice/BusRoutes"
DATAMALL_BUS_STOPS = "https://datamall2.mytransport.sg/ltaodataservice/BusStops"
DATAMALL_TRAFFIC_INCIDENTS = "https://datamall2.mytransport.sg/ltaodataservice/TrafficIncidents"
DATAMALL_TRAFFIC_SPEED_BANDS = "https://datamall2.mytransport.sg/ltaodataservice/v4/TrafficSpeedBands"
RAINFALL_API_URL = "https://api.data.gov.sg/v1/environment/rainfall"

# API Credentials (from environment)
LTA_DATAMALL_KEY = os.getenv("LTA_DATAMALL")

# Singapore UTM zone for coordinate transformations
SINGAPORE_UTM = 'EPSG:32648'  # UTM Zone 48N
WGS84 = 'EPSG:4326'
