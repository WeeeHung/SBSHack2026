"""
AI Predictor service (dummy implementation for now).
"""
from typing import Dict, Any, List, Optional


def to_float(value, default=0.0):
    """Convert value to float, handling strings and None."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def predict_speed(current_link: Dict[str, Any], 
                 next_links: List[Dict[str, Any]],
                 speed_bands: Dict[str, Any],
                 has_rain: bool,
                 has_incident: bool) -> float:
    """
    Predict speed for the next link.
    
    Dummy implementation: returns the speed of the next link from speed_bands data.
    
    Args:
        current_link: Current link dictionary
        next_links: List of next few links
        speed_bands: Speed band data dictionary
        has_rain: Boolean indicating if there's rain
        has_incident: Boolean indicating if there's an incident
    
    Returns:
        Predicted speed in km/h
    """
    print(f"[predict_speed] current_link: {current_link}")
    print(f"[predict_speed] next_links: {next_links}")
    print(f"[predict_speed] speed_bands: {speed_bands}")
    print(f"[predict_speed] has_rain: {has_rain}")
    print(f"[predict_speed] has_incident: {has_incident}")
    
    # For now, just return the speed of the next link
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
