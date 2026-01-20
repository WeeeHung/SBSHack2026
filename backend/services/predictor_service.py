"""
AI Predictor service using trained speedband prediction model.
"""
import os
import sys
from typing import Dict, Any, List, Optional

# Add parent directory to path to import speedband_model
ROOT_DIR = os.path.dirname(os.path.abspath(os.path.join(__file__, os.pardir, os.pardir)))
TRAINING_DATA_DIR = os.path.join(ROOT_DIR, "training_data")
sys.path.insert(0, TRAINING_DATA_DIR)

try:
    from speedband_model import get_predictor, SpeedbandPredictor
    MODEL_AVAILABLE = True
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


def predict_speed(current_link: Dict[str, Any], 
                 next_links: List[Dict[str, Any]],
                 speed_bands: Dict[str, Any],
                 has_rain: bool,
                 has_incident: bool) -> float:
    """
    Predict speed for the next link using trained ML model.
    
    Args:
        current_link: Current link dictionary
        next_links: List of next few links
        speed_bands: Speed band data dictionary (current and historical)
        has_rain: Boolean indicating if there's rain
        has_incident: Boolean indicating if there's an incident
    
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
            target_link_id = str(current_link.get('LinkID', ''))
        else:
            # Predict for the first next link
            target_link_id = str(next_links[0].get('LinkID', ''))
        
        if not target_link_id:
            return 0.0
        
        # Get predictor
        predictor = get_predictor()
        
        # Build speedband history from speed_bands data
        # We need to extract historical speedband values for this link
        # For now, use current speedband if available, otherwise use defaults
        current_speedband = None
        if target_link_id in speed_bands:
            speed_data = speed_bands[target_link_id]
            # Try to get speedband from the data structure
            if isinstance(speed_data, dict):
                # If speed_bands contains speedband directly
                if 'SpeedBand' in speed_data:
                    current_speedband = int(speed_data['SpeedBand'])
                # Or if it's the current link's speedband
                elif 'speedband' in speed_data:
                    current_speedband = int(speed_data['speedband'])
        
        # If we don't have current speedband, try to infer from min/max speed
        if current_speedband is None and target_link_id in speed_bands:
            speed_data = speed_bands[target_link_id]
            if isinstance(speed_data, dict):
                min_speed = to_float(speed_data.get('minspeed'), 0.0)
                max_speed = to_float(speed_data.get('maxspeed'), 0.0)
                avg_speed = (min_speed + max_speed) / 2 if max_speed > 0 else 0.0
                # Rough mapping from speed to speedband
                if avg_speed < 10:
                    current_speedband = 0
                elif avg_speed < 20:
                    current_speedband = 1
                elif avg_speed < 30:
                    current_speedband = 2
                elif avg_speed < 40:
                    current_speedband = 3
                elif avg_speed < 50:
                    current_speedband = 4
                elif avg_speed < 60:
                    current_speedband = 5
                elif avg_speed < 70:
                    current_speedband = 6
                elif avg_speed < 80:
                    current_speedband = 7
                else:
                    current_speedband = 8
        
        # Default speedband if still None
        if current_speedband is None:
            current_speedband = 3  # Default to middle value
        
        # Build history (use current value repeated if no history available)
        # In production, this should come from a historical data store
        speedband_history = [current_speedband] * 5  # Use last 5 values (simplified)
        
        # Build rainfall history
        rainfall_history = [1.0 if has_rain else 0.0] * 5
        
        # Build incident history
        incident_history = [has_incident] * 5
        
        # Predict next speedband
        predicted_speedband = predictor.predict(
            link_id=target_link_id,
            speedband_history=speedband_history,
            rainfall_history=rainfall_history,
            incident_history=incident_history
        )
        
        # Convert speedband to speed
        predicted_speed = speedband_to_speed(predicted_speedband)
        
        return predicted_speed
        
    except Exception as e:
        print(f"Error in ML prediction: {e}")
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
