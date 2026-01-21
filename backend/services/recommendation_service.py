"""
Service for generating coasting recommendations based on predicted traffic conditions.
"""
from typing import Dict, Any, Optional, Tuple
from enum import Enum


class DriverAction(str, Enum):
    """Driver action recommendations."""
    MAINTAIN_SPEED = "maintain_speed"
    COAST = "coast"
    SPEED_UP = "speed_up"
    CRAWL = "crawl"


class UrgencyLevel(str, Enum):
    """Urgency level for recommendations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Speed thresholds (in km/h)
FAST_SPEED_THRESHOLD = 50.0  # Above this is considered "fast"
SLOW_SPEED_THRESHOLD = 30.0  # Below this is considered "slow"
SPEED_DIFFERENCE_THRESHOLD = 15.0  # Significant speed difference


def get_current_link_speed(current_link: Dict[str, Any], 
                          speed_bands: Dict[str, Any]) -> float:
    """
    Get the current speed for the current link.
    
    Args:
        current_link: Current link dictionary
        speed_bands: Speed band data dictionary
    
    Returns:
        Current speed in km/h
    """
    current_link_id = str(current_link.get('LinkID', ''))
    if current_link_id in speed_bands:
        speed_data = speed_bands[current_link_id]
        min_speed = float(speed_data.get('minspeed', 0) or 0)
        max_speed = float(speed_data.get('maxspeed', 0) or 0)
        if max_speed > 0:
            return (min_speed + max_speed) / 2.0
    
    # Fallback: try to extract from speedband
    if current_link_id in speed_bands:
        speed_data = speed_bands[current_link_id]
        speedband = speed_data.get('speedband')
        if speedband is not None:
            from backend.services.predictor_service import speedband_to_speed
            return speedband_to_speed(int(speedband))
    
    return 0.0


def generate_recommendation(
    current_link: Dict[str, Any],
    predicted_speed: float,
    speed_bands: Dict[str, Any],
    has_rain: bool,
    has_incident: bool
) -> Dict[str, Any]:
    """
    Generate coasting recommendation based on current and predicted conditions.
    
    Implements the logic from TODO.md:
    - If current + next link is fast: maintain speed
    - If current link is fast, next link starts to slow down: speed up (if can pass before slowdown)
    - If current link is fast, next link is slow: start coasting early (earlier if raining)
    - If both links are slow: crawl
    
    Args:
        current_link: Current link dictionary
        predicted_speed: Predicted speed for next link (km/h)
        speed_bands: Speed band data dictionary
        has_rain: Boolean indicating if there's rain
        has_incident: Boolean indicating if there's an incident
    
    Returns:
        Dictionary with recommendation details:
        - action: One of "maintain_speed", "coast", "speed_up", "crawl"
        - current_speed: Current link speed (km/h)
        - predicted_speed: Predicted next link speed (km/h)
        - reasoning: Text explanation
        - urgency: "low", "medium", or "high"
        - color_cue: Color for visual display ("green", "yellow", "orange", "red")
    """
    # Get current link speed
    current_speed = get_current_link_speed(current_link, speed_bands)
    
    # Determine if current and predicted speeds are fast/slow
    current_is_fast = current_speed >= FAST_SPEED_THRESHOLD
    current_is_slow = current_speed <= SLOW_SPEED_THRESHOLD
    predicted_is_fast = predicted_speed >= FAST_SPEED_THRESHOLD
    predicted_is_slow = predicted_speed <= SLOW_SPEED_THRESHOLD
    speed_difference = current_speed - predicted_speed
    
    # Decision logic based on TODO.md rules
    action = None
    reasoning = ""
    urgency = UrgencyLevel.MEDIUM
    color_cue = "green"
    
    # Rule 1: If current + next link is fast: maintain speed
    if current_is_fast and predicted_is_fast:
        action = DriverAction.MAINTAIN_SPEED
        reasoning = f"Both current ({current_speed:.0f} km/h) and next link ({predicted_speed:.0f} km/h) are fast. Maintain current speed."
        urgency = UrgencyLevel.LOW
        color_cue = "green"
    
    # Rule 2: If current link is fast, next link starts to slow down: speed up (if can pass before slowdown)
    elif current_is_fast and not predicted_is_fast and speed_difference > SPEED_DIFFERENCE_THRESHOLD:
        # Check if the slowdown is significant enough to warrant speeding up
        # This assumes the bus can pass the next link before it fully slows down
        action = DriverAction.SPEED_UP
        reasoning = f"Current link is fast ({current_speed:.0f} km/h) but next link will slow to {predicted_speed:.0f} km/h. Speed up to pass before slowdown."
        urgency = UrgencyLevel.MEDIUM
        color_cue = "orange"
    
    # Rule 3: If current link is fast, next link is slow: start coasting early (earlier if raining)
    elif current_is_fast and predicted_is_slow:
        action = DriverAction.COAST
        if has_rain:
            reasoning = f"Current link is fast ({current_speed:.0f} km/h) but next link is slow ({predicted_speed:.0f} km/h). Rain detected - start coasting early."
            urgency = UrgencyLevel.HIGH
        elif has_incident:
            reasoning = f"Current link is fast ({current_speed:.0f} km/h) but next link is slow ({predicted_speed:.0f} km/h). Incident ahead - start coasting early."
            urgency = UrgencyLevel.HIGH
        else:
            reasoning = f"Current link is fast ({current_speed:.0f} km/h) but next link is slow ({predicted_speed:.0f} km/h). Start coasting to avoid braking."
            urgency = UrgencyLevel.MEDIUM
        color_cue = "yellow"
    
    # Rule 4: If both links are slow: crawl
    elif current_is_slow and predicted_is_slow:
        action = DriverAction.CRAWL
        reasoning = f"Both current ({current_speed:.0f} km/h) and next link ({predicted_speed:.0f} km/h) are slow. Continue at slow speed."
        urgency = UrgencyLevel.LOW
        color_cue = "red"
    
    # Default/edge cases
    elif current_is_slow and predicted_is_fast:
        # Slow now, fast ahead - can accelerate
        action = DriverAction.SPEED_UP
        reasoning = f"Current link is slow ({current_speed:.0f} km/h) but next link will be fast ({predicted_speed:.0f} km/h). Prepare to accelerate."
        urgency = UrgencyLevel.LOW
        color_cue = "orange"
    
    elif not current_is_fast and not current_is_slow and not predicted_is_fast and not predicted_is_slow:
        # Both are medium speed - maintain
        action = DriverAction.MAINTAIN_SPEED
        reasoning = f"Current ({current_speed:.0f} km/h) and next link ({predicted_speed:.0f} km/h) are at moderate speeds. Maintain current speed."
        urgency = UrgencyLevel.LOW
        color_cue = "green"
    
    else:
        # Fallback: maintain speed
        action = DriverAction.MAINTAIN_SPEED
        reasoning = f"Current speed: {current_speed:.0f} km/h, Predicted next: {predicted_speed:.0f} km/h. Maintain current speed."
        urgency = UrgencyLevel.LOW
        color_cue = "green"
    
    return {
        "action": action.value,
        "current_speed": round(current_speed, 1),
        "predicted_speed": round(predicted_speed, 1),
        "reasoning": reasoning,
        "urgency": urgency.value,
        "color_cue": color_cue,
        "has_rain": has_rain,
        "has_incident": has_incident
    }
