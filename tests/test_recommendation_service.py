"""
Unit tests for the recommendation service.
"""
import pytest
from backend.services.recommendation_service import (
    generate_recommendation,
    get_current_link_speed,
    DriverAction,
    UrgencyLevel,
    FAST_SPEED_THRESHOLD,
    SLOW_SPEED_THRESHOLD
)


def test_fast_current_fast_next_maintain_speed():
    """Test: Fast current + fast next → Maintain Speed"""
    current_link = {'LinkID': '12345'}
    speed_bands = {
        '12345': {
            'minspeed': 60,
            'maxspeed': 70,
            'speedband': 6
        }
    }
    predicted_speed = 65.0
    has_rain = False
    has_incident = False
    
    result = generate_recommendation(
        current_link, predicted_speed, speed_bands, has_rain, has_incident
    )
    
    assert result['action'] == DriverAction.MAINTAIN_SPEED.value
    assert result['urgency'] == UrgencyLevel.LOW.value
    assert result['color_cue'] == 'green'
    assert 'maintain' in result['reasoning'].lower()


def test_fast_current_slow_next_coast():
    """Test: Fast current + slow next → Coast"""
    current_link = {'LinkID': '12345'}
    speed_bands = {
        '12345': {
            'minspeed': 60,
            'maxspeed': 70,
            'speedband': 6
        }
    }
    predicted_speed = 25.0
    has_rain = False
    has_incident = False
    
    result = generate_recommendation(
        current_link, predicted_speed, speed_bands, has_rain, has_incident
    )
    
    assert result['action'] == DriverAction.COAST.value
    assert result['urgency'] == UrgencyLevel.MEDIUM.value
    assert result['color_cue'] == 'yellow'
    assert 'coast' in result['reasoning'].lower()


def test_fast_current_slow_next_coast_with_rain():
    """Test: Fast current + slow next + rain → Coast (earlier, high urgency)"""
    current_link = {'LinkID': '12345'}
    speed_bands = {
        '12345': {
            'minspeed': 60,
            'maxspeed': 70,
            'speedband': 6
        }
    }
    predicted_speed = 25.0
    has_rain = True
    has_incident = False
    
    result = generate_recommendation(
        current_link, predicted_speed, speed_bands, has_rain, has_incident
    )
    
    assert result['action'] == DriverAction.COAST.value
    assert result['urgency'] == UrgencyLevel.HIGH.value
    assert result['color_cue'] == 'yellow'
    assert result['has_rain'] == True
    assert 'rain' in result['reasoning'].lower() or 'early' in result['reasoning'].lower()


def test_fast_current_slow_next_coast_with_incident():
    """Test: Fast current + slow next + incident → Coast (high urgency)"""
    current_link = {'LinkID': '12345'}
    speed_bands = {
        '12345': {
            'minspeed': 60,
            'maxspeed': 70,
            'speedband': 6
        }
    }
    predicted_speed = 25.0
    has_rain = False
    has_incident = True
    
    result = generate_recommendation(
        current_link, predicted_speed, speed_bands, has_rain, has_incident
    )
    
    assert result['action'] == DriverAction.COAST.value
    assert result['urgency'] == UrgencyLevel.HIGH.value
    assert result['has_incident'] == True
    assert 'incident' in result['reasoning'].lower() or 'early' in result['reasoning'].lower()


def test_slow_current_slow_next_crawl():
    """Test: Slow current + slow next → Crawl"""
    current_link = {'LinkID': '12345'}
    speed_bands = {
        '12345': {
            'minspeed': 15,
            'maxspeed': 25,
            'speedband': 1
        }
    }
    predicted_speed = 20.0
    has_rain = False
    has_incident = False
    
    result = generate_recommendation(
        current_link, predicted_speed, speed_bands, has_rain, has_incident
    )
    
    assert result['action'] == DriverAction.CRAWL.value
    assert result['urgency'] == UrgencyLevel.LOW.value
    assert result['color_cue'] == 'red'
    assert 'slow' in result['reasoning'].lower() or 'crawl' in result['reasoning'].lower()


def test_fast_current_slowing_next_speed_up():
    """Test: Fast current + slowing next (significant difference) → Speed Up"""
    current_link = {'LinkID': '12345'}
    speed_bands = {
        '12345': {
            'minspeed': 60,
            'maxspeed': 70,
            'speedband': 6
        }
    }
    # Predicted speed is significantly lower but not "slow" - represents slowing down
    predicted_speed = 40.0  # Below fast threshold, significant difference
    has_rain = False
    has_incident = False
    
    result = generate_recommendation(
        current_link, predicted_speed, speed_bands, has_rain, has_incident
    )
    
    assert result['action'] == DriverAction.SPEED_UP.value
    assert result['color_cue'] == 'orange'
    assert 'speed up' in result['reasoning'].lower() or 'pass' in result['reasoning'].lower()


def test_slow_current_fast_next_speed_up():
    """Test: Slow current + fast next → Speed Up"""
    current_link = {'LinkID': '12345'}
    speed_bands = {
        '12345': {
            'minspeed': 15,
            'maxspeed': 25,
            'speedband': 1
        }
    }
    predicted_speed = 65.0
    has_rain = False
    has_incident = False
    
    result = generate_recommendation(
        current_link, predicted_speed, speed_bands, has_rain, has_incident
    )
    
    assert result['action'] == DriverAction.SPEED_UP.value
    assert result['color_cue'] == 'orange'
    assert 'accelerate' in result['reasoning'].lower() or 'fast' in result['reasoning'].lower()


def test_medium_speeds_maintain():
    """Test: Medium current + medium next → Maintain Speed"""
    current_link = {'LinkID': '12345'}
    speed_bands = {
        '12345': {
            'minspeed': 40,
            'maxspeed': 45,
            'speedband': 4
        }
    }
    predicted_speed = 42.0
    has_rain = False
    has_incident = False
    
    result = generate_recommendation(
        current_link, predicted_speed, speed_bands, has_rain, has_incident
    )
    
    assert result['action'] == DriverAction.MAINTAIN_SPEED.value
    assert result['color_cue'] == 'green'


def test_get_current_link_speed_from_min_max():
    """Test getting current link speed from min/max speeds"""
    current_link = {'LinkID': '12345'}
    speed_bands = {
        '12345': {
            'minspeed': 50,
            'maxspeed': 60
        }
    }
    
    speed = get_current_link_speed(current_link, speed_bands)
    assert speed == 55.0


def test_get_current_link_speed_from_speedband():
    """Test getting current link speed from speedband when min/max not available"""
    current_link = {'LinkID': '12345'}
    speed_bands = {
        '12345': {
            'speedband': 5  # Should map to ~55 km/h
        }
    }
    
    speed = get_current_link_speed(current_link, speed_bands)
    assert speed > 0
    assert speed <= 85.0


def test_get_current_link_speed_no_data():
    """Test getting current link speed when no data available"""
    current_link = {'LinkID': '12345'}
    speed_bands = {}
    
    speed = get_current_link_speed(current_link, speed_bands)
    assert speed == 0.0


def test_recommendation_returns_all_fields():
    """Test that recommendation returns all required fields"""
    current_link = {'LinkID': '12345'}
    speed_bands = {
        '12345': {
            'minspeed': 60,
            'maxspeed': 70
        }
    }
    predicted_speed = 65.0
    has_rain = False
    has_incident = False
    
    result = generate_recommendation(
        current_link, predicted_speed, speed_bands, has_rain, has_incident
    )
    
    required_fields = ['action', 'current_speed', 'predicted_speed', 'reasoning', 
                      'urgency', 'color_cue', 'has_rain', 'has_incident']
    for field in required_fields:
        assert field in result, f"Missing field: {field}"
    
    assert isinstance(result['current_speed'], (int, float))
    assert isinstance(result['predicted_speed'], (int, float))
    assert isinstance(result['reasoning'], str)
    assert result['action'] in [a.value for a in DriverAction]
    assert result['urgency'] in [u.value for u in UrgencyLevel]
    assert result['color_cue'] in ['green', 'yellow', 'orange', 'red']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
