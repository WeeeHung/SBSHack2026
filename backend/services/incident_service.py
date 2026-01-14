"""
Service for fetching and checking traffic incidents.
"""
import requests
from typing import Dict, Any, List
import math
from dotenv import load_dotenv
import os

from backend.config import DATAMALL_TRAFFIC_INCIDENTS, LTA_DATAMALL_KEY, RAINFALL_RADIUS_METERS

# Load environment variables
load_dotenv()


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


def fetch_incidents() -> Dict[str, Any]:
    """
    Fetch traffic incidents from LTA DataMall API.
    
    Returns:
        API response containing traffic incidents
    """
    headers = {
        "AccountKey": LTA_DATAMALL_KEY,
        "accept": "application/json"
    }
    
    try:
        response = requests.get(DATAMALL_TRAFFIC_INCIDENTS, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching traffic incidents: {e}")
        raise


def check_incidents_in_links(links: List[Dict[str, Any]], 
                            incidents_data: Dict[str, Any]) -> bool:
    """
    Check if any incident is within 50m radius of any link.
    
    Args:
        links: List of link dictionaries
        incidents_data: Traffic incidents API response
    
    Returns:
        True if any incident found in any of the links
    """
    incidents = incidents_data.get('value', [])
    if not incidents:
        return False
    
    # Check each link
    for link in links:
        link_midpoint = get_link_midpoint(link)
        if link_midpoint is None:
            continue
        
        link_lat, link_lon = link_midpoint
        
        # Check each incident
        for incident in incidents:
            incident_lat = incident.get('Latitude')
            incident_lon = incident.get('Longitude')
            
            if incident_lat is None or incident_lon is None:
                continue
            
            distance = haversine_distance(link_lat, link_lon, 
                                        incident_lat, incident_lon)
            if distance <= RAINFALL_RADIUS_METERS:
                return True
    
    return False
