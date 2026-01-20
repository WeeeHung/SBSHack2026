"""
AI Predictor service using trained speedband prediction model.
"""
import os
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime
import math

# Add parent directory to path to import speedband_model
ROOT_DIR = os.path.dirname(os.path.abspath(os.path.join(__file__, os.pardir, os.pardir)))
TRAINING_DATA_DIR = os.path.join(ROOT_DIR, "training_data")
sys.path.insert(0, TRAINING_DATA_DIR)

try:
    from speedband_model import get_predictor, SpeedbandPredictor
    MODEL_AVAILABLE = True
    print("Speedband model loaded successfully.")
except (ImportError, FileNotFoundError) as e:
    print(f"Warning: Could not load speedband model: {e}")
    print("Falling back to dummy implementation.")
    MODEL_AVAILABLE = False
    SpeedbandPredictor = None


def to_float(value, default=0.0):
    """Convert value to float, handling strings and None."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


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


def get_link_midpoint(link: Dict[str, Any]) -> Optional[tuple]:
    """Get the midpoint coordinates of a link."""
    try:
        # Try different possible key names
        start_lat = float(link.get('StartLat') or link.get('start_lat', 0))
        start_lon = float(link.get('StartLon') or link.get('start_lon', 0))
        end_lat = float(link.get('EndLat') or link.get('end_lat', 0))
        end_lon = float(link.get('EndLon') or link.get('end_lon', 0))
        
        if start_lat == 0 and start_lon == 0 and end_lat == 0 and end_lon == 0:
            return None
            
        mid_lat = (start_lat + end_lat) / 2
        mid_lon = (start_lon + end_lon) / 2
        return (mid_lat, mid_lon)
    except (ValueError, KeyError, TypeError):
        return None


def get_rainfall_for_link(link: Dict[str, Any], rainfall_data: Dict[str, Any], radius_meters: float = 50.0) -> float:
    """
    Get rainfall value in mm for a specific link.
    
    Args:
        link: Link dictionary
        rainfall_data: Rainfall API response
        radius_meters: Radius to search for rainfall stations
    
    Returns:
        Rainfall value in mm (0.0 if no rain found)
    """
    if not rainfall_data:
        return 0.0
    
    # Extract rainfall readings and stations
    items = rainfall_data.get('items', [])
    if not items:
        return 0.0
    
    # Get the latest readings
    latest_item = items[0] if items else {}
    readings = latest_item.get('readings', [])
    
    if not readings:
        return 0.0
    
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
    
    # Get link midpoint
    link_midpoint = get_link_midpoint(link)
    if link_midpoint is None:
        return 0.0
    
    link_lat, link_lon = link_midpoint
    
    # Find nearest station with rainfall
    nearest_rainfall = 0.0
    min_distance = float('inf')
    
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
        
        # Calculate distance
        distance = haversine_distance(link_lat, link_lon, station_lat, station_lon)
        
        # If within radius and closer than previous, use this value
        if distance <= radius_meters and distance < min_distance:
            nearest_rainfall = rainfall_value
            min_distance = distance
    
    return nearest_rainfall


def speedband_to_speed(speedband: int) -> float:
    """
    Convert speedband value to approximate speed in km/h.
    
    Speedband mapping (approximate):
    0: 0-10 km/h
    1: 10-20 km/h
    2: 20-30 km/h
    3: 30-40 km/h
    4: 40-50 km/h
    5: 50-60 km/h
    6: 60-70 km/h
    7: 70-80 km/h
    8: 80+ km/h
    """
    # Use midpoint of each band
    speed_mapping = {
        0: 5.0,
        1: 15.0,
        2: 25.0,
        3: 35.0,
        4: 45.0,
        5: 55.0,
        6: 65.0,
        7: 75.0,
        8: 85.0
    }
    return speed_mapping.get(int(speedband), 35.0)


def extract_speedband_from_data(speed_data: Dict[str, Any]) -> Optional[int]:
    """
    Extract speedband value from speed data dictionary.
    
    Args:
        speed_data: Speed band data dictionary
    
    Returns:
        Speedband value (0-8) or None if not found
    """
    if not isinstance(speed_data, dict):
        return None
    
    # Try different possible key names
    speedband = speed_data.get('SpeedBand') or speed_data.get('speedband')
    if speedband is not None:
        try:
            return int(speedband)
        except (ValueError, TypeError):
            pass
    
    # If no direct speedband, try to infer from min/max speed
    min_speed = to_float(speed_data.get('minspeed') or speed_data.get('MinimumSpeed'), 0.0)
    max_speed = to_float(speed_data.get('maxspeed') or speed_data.get('MaximumSpeed'), 0.0)
    
    if max_speed > 0:
        avg_speed = (min_speed + max_speed) / 2
        # Rough mapping from speed to speedband
        if avg_speed < 10:
            return 0
        elif avg_speed < 20:
            return 1
        elif avg_speed < 30:
            return 2
        elif avg_speed < 40:
            return 3
        elif avg_speed < 50:
            return 4
        elif avg_speed < 60:
            return 5
        elif avg_speed < 70:
            return 6
        elif avg_speed < 80:
            return 7
        else:
            return 8
    
    return None


def build_speedband_history(
    target_link: Dict[str, Any],
    current_link: Dict[str, Any],
    next_links: List[Dict[str, Any]],
    speed_bands: Dict[str, Any],
    min_history_length: int = 5,
) -> List[int]:
    """
    Build speedband history for prediction using ONLY:
      - target link
      - inbound links of target
      - outbound links of target
      - current link and next links list
    """
    history: List[int] = []

    target_link_id = str(target_link.get("LinkID", ""))

    # Collect candidate LinkIDs in an ordered list:
    candidate_ids: List[str] = []

    # 1) Inbound neighbours of target
    inbound_ids = target_link.get("inbound_link_ids", []) or []
    candidate_ids.extend(str(lid) for lid in inbound_ids)

    # 2) Current link
    current_id = str(current_link.get("LinkID", ""))
    if current_id:
        candidate_ids.append(current_id)

    # 3) Target link itself
    if target_link_id:
        candidate_ids.append(target_link_id)

    # 4) Next links along the route
    for link in next_links:
        link_id = str(link.get("LinkID", ""))
        if link_id:
            candidate_ids.append(link_id)

    # 5) Outbound neighbours of target
    outbound_ids = target_link.get("outbound_link_ids", []) or []
    candidate_ids.extend(str(lid) for lid in outbound_ids)

    # De-duplicate while preserving order
    seen: set = set()
    ordered_ids: List[str] = []
    for lid in candidate_ids:
        if lid and lid not in seen:
            seen.add(lid)
            ordered_ids.append(lid)

    # Build history from these IDs
    for lid in ordered_ids:
        if lid in speed_bands:
            speedband = extract_speedband_from_data(speed_bands[lid])
            if speedband is not None:
                # Avoid immediate duplicates to keep history informative
                if not history or history[-1] != speedband:
                    history.append(speedband)
                    if len(history) >= min_history_length:
                        break

    # If we still don't have enough history, pad with the last value
    if history:
        while len(history) < min_history_length:
            history.append(history[-1])
    else:
        # Default to middle value if no data available
        history = [3] * min_history_length

    return history


def predict_speed(current_link: Dict[str, Any], 
                 next_links: List[Dict[str, Any]],
                 speed_bands: Dict[str, Any],
                 has_rain: bool,
                 has_incident: bool,
                 rainfall_data: Optional[Dict[str, Any]] = None,
                 links_for_analysis: Optional[List[Dict[str, Any]]] = None) -> float:
    """
    Predict speed for the next link using trained ML model.
    
    Args:
        current_link: Current link dictionary
        next_links: List of next few links
        speed_bands: Speed band data dictionary (current and historical)
        has_rain: Boolean indicating if there's rain
        has_incident: Boolean indicating if there's an incident
        rainfall_data: Optional rainfall data for extracting actual rainfall values
        links_for_analysis: Optional list of all links for analysis (for building history)
    
    Returns:
        Predicted speed in km/h
    """
    if not MODEL_AVAILABLE:
        # Fallback to dummy implementation
        return _predict_speed_dummy(current_link, next_links, speed_bands, has_rain, has_incident)
    
    try:
        # Get the link we want to predict for
        if not next_links:
            # If no next links, predict for current link
            target_link = current_link
            target_link_id = str(current_link.get('LinkID', ''))
        else:
            # Predict for the first next link
            target_link = next_links[0]
            target_link_id = str(next_links[0].get('LinkID', ''))
        
        if not target_link_id:
            return 0.0
        
        # Get predictor
        predictor = get_predictor()
        
        # Build speedband history (restricted to target, inbound/outbound, and current/next links)
        speedband_history = build_speedband_history(
            target_link=target_link,
            current_link=current_link,
            next_links=next_links,
            speed_bands=speed_bands,
        )
        
        # Build rainfall history
        if rainfall_data:
            # Get actual rainfall values for links
            rainfall_values = []
            all_links_for_rain = [current_link] + next_links
            for link in all_links_for_rain[-5:]:  # Use last 5 links
                rainfall_mm = get_rainfall_for_link(link, rainfall_data)
                rainfall_values.append(rainfall_mm)
            
            # Pad or trim to match speedband history length
            while len(rainfall_values) < len(speedband_history):
                rainfall_values.append(rainfall_values[-1] if rainfall_values else 0.0)
            rainfall_history = rainfall_values[:len(speedband_history)]
        else:
            # Fallback to boolean-based values
            rainfall_history = [1.0 if has_rain else 0.0] * len(speedband_history)
        
        # Build incident history
        incident_history = [has_incident] * len(speedband_history)
        
        # Get current time
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute
        
        # Predict next speedband
        predicted_speedband = predictor.predict(
            link_id=target_link_id,
            speedband_history=speedband_history,
            rainfall_history=rainfall_history,
            incident_history=incident_history,
            current_hour=current_hour,
            current_minute=current_minute
        )
        
        # Convert speedband to speed
        predicted_speed = speedband_to_speed(predicted_speedband)
        
        return predicted_speed
        
    except Exception as e:
        print(f"Error in ML prediction: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to dummy implementation
        return _predict_speed_dummy(current_link, next_links, speed_bands, has_rain, has_incident)


def _predict_speed_dummy(current_link: Dict[str, Any], 
                         next_links: List[Dict[str, Any]],
                         speed_bands: Dict[str, Any],
                         has_rain: bool,
                         has_incident: bool) -> float:
    """
    Dummy implementation: returns the speed of the next link from speed_bands data.
    Used as fallback when model is not available.
    """
    if not next_links:
        # If no next links, use current link's speed
        current_link_id = str(current_link.get('LinkID', ''))
        if current_link_id in speed_bands:
            speed_data = speed_bands[current_link_id]
            # Return average of min and max speed
            min_speed = to_float(speed_data.get('minspeed'), 0.0)
            max_speed = to_float(speed_data.get('maxspeed'), 0.0)
            return (min_speed + max_speed) / 2 if max_speed > 0 else 0.0
        return 0.0
    
    # Get the first next link
    next_link = next_links[0]
    next_link_id = str(next_link.get('LinkID', ''))
    
    if next_link_id in speed_bands:
        speed_data = speed_bands[next_link_id]
        min_speed = to_float(speed_data.get('minspeed'), 0.0)
        max_speed = to_float(speed_data.get('maxspeed'), 0.0)
        # Return average of min and max speed
        predicted = (min_speed + max_speed) / 2 if max_speed > 0 else 0.0
        
        # Simple adjustments based on conditions (dummy logic)
        if has_rain:
            predicted *= 0.8  # Reduce speed by 20% if raining
        if has_incident:
            predicted *= 0.6  # Reduce speed by 40% if incident
        
        return max(0.0, predicted)
    
    return 0.0
