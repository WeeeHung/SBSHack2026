"""
Service for fetching and checking rainfall data.
"""
import requests
from typing import Dict, Any, List
import math

from backend.config import RAINFALL_API_URL, RAINFALL_RADIUS_METERS


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points in meters."""
    R = 6371000
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def get_link_midpoint(link: Dict[str, Any]) -> tuple:
    """Get the midpoint coordinates of a link."""
    try:
        start_lat = float(link['StartLat'])
        start_lon = float(link['StartLon'])
        end_lat = float(link['EndLat'])
        end_lon = float(link['EndLon'])
        mid_lat = (start_lat + end_lat) / 2
        mid_lon = (start_lon + end_lon) / 2
        return (mid_lat, mid_lon)
    except (ValueError, KeyError):
        return None


def fetch_rainfall_data() -> Dict[str, Any]:
    """
    Fetch rainfall data from data.gov.sg API.
    
    Returns:
        API response containing rainfall information
    """
    try:
        response = requests.get(RAINFALL_API_URL)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching rainfall data: {e}")
        raise


def check_rain_in_links(links: List[Dict[str, Any]], 
                        rainfall_data: Dict[str, Any]) -> bool:
    """
    Check if any link has rain within 50m radius.
    
    Args:
        links: List of link dictionaries
        rainfall_data: Rainfall API response
    
    Returns:
        True if any link has rain within 50m radius
    """
    # Extract rainfall readings and stations
    items = rainfall_data.get('items', [])
    if not items:
        return False
    
    # Get the latest readings
    latest_item = items[0] if items else {}
    readings = latest_item.get('readings', [])
    
    if not readings:
        return False
    
    # Build station location map from metadata
    stations_map = {}
    metadata = rainfall_data.get('metadata', {})
    stations = metadata.get('stations', [])
    for station in stations:
        station_id = station.get('id')
        location = station.get('location', {})
        if station_id and location:
            stations_map[station_id] = {
                'latitude': location.get('latitude'),
                'longitude': location.get('longitude')
            }
    
    # Check each link
    for link in links:
        link_midpoint = get_link_midpoint(link)
        if link_midpoint is None:
            continue
        
        link_lat, link_lon = link_midpoint
        
        # Check each rainfall reading
        for reading in readings:
            station_id = reading.get('station_id')
            rainfall_value = reading.get('value', 0)
            
            if not station_id or rainfall_value <= 0:
                continue
            
            # Get station location from map
            station_info = stations_map.get(station_id)
            if not station_info:
                continue
            
            station_lat = station_info.get('latitude')
            station_lon = station_info.get('longitude')
            
            if station_lat is None or station_lon is None:
                continue
            
            # Check if station is within radius
            distance = haversine_distance(link_lat, link_lon, 
                                          station_lat, station_lon)
            if distance <= RAINFALL_RADIUS_METERS:
                return True
    
    return False
