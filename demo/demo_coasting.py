"""
Demo script to showcase the predictive coasting system.
Demonstrates various scenarios and recommendations.
"""
import requests
import json
import time
from typing import Dict, Any

API_BASE_URL = "http://localhost:8000"


def print_recommendation(recommendation: Dict[str, Any], scenario_name: str):
    """Pretty print a recommendation."""
    print("\n" + "=" * 80)
    print(f"SCENARIO: {scenario_name}")
    print("=" * 80)
    print(f"Action:        {recommendation['action'].upper()}")
    print(f"Current Speed: {recommendation['current_speed']} km/h")
    print(f"Predicted:     {recommendation['predicted_speed']} km/h")
    print(f"Urgency:       {recommendation['urgency'].upper()}")
    print(f"Color Cue:     {recommendation['color_cue'].upper()}")
    print(f"Rain:          {'Yes' if recommendation['has_rain'] else 'No'}")
    print(f"Incident:      {'Yes' if recommendation['has_incident'] else 'No'}")
    print(f"\nReasoning: {recommendation['reasoning']}")
    print("=" * 80)


def demo_scenario(bus_no: int, direction: int, lat: float, lon: float, scenario_name: str):
    """Fetch and display a recommendation for a scenario."""
    try:
        url = f"{API_BASE_URL}/coasting_recommendation"
        params = {
            "bus_no": bus_no,
            "direction": direction,
            "lat": lat,
            "lon": lon
        }
        
        print(f"\nFetching recommendation for Bus {bus_no}, Direction {direction}...")
        print(f"Location: ({lat}, {lon})")
        
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            recommendation = response.json()
            print_recommendation(recommendation, scenario_name)
            return recommendation
        else:
            print(f"Error: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to API.")
        print("Make sure the backend server is running:")
        print("  python backend/main.py")
        return None
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return None


def main():
    """Run demo scenarios."""
    print("\n" + "=" * 80)
    print("PREDICTIVE COASTING SYSTEM - DEMO")
    print("=" * 80)
    print("\nThis demo showcases various scenarios for the predictive coasting system.")
    print("The system analyzes current and predicted traffic conditions to recommend")
    print("driver actions: Maintain Speed, Coast, Speed Up, or Crawl.\n")
    
    # Example coordinates for Bus 147, Direction 1 in Singapore
    # These are approximate coordinates along the route
    scenarios = [
        {
            "name": "Bus 147 Direction 1 - Start of Route",
            "bus_no": 147,
            "direction": 1,
            "lat": 1.3521,
            "lon": 103.8198
        },
        {
            "name": "Bus 147 Direction 1 - Mid Route",
            "bus_no": 147,
            "direction": 1,
            "lat": 1.3450,
            "lon": 103.8300
        },
        {
            "name": "Bus 190 Direction 1 - Example Location",
            "bus_no": 190,
            "direction": 1,
            "lat": 1.3500,
            "lon": 103.8250
        },
        {
            "name": "Bus 960 Direction 1 - Example Location",
            "bus_no": 960,
            "direction": 1,
            "lat": 1.3600,
            "lon": 103.8150
        }
    ]
    
    print("\nAvailable scenarios:")
    for i, scenario in enumerate(scenarios, 1):
        print(f"  {i}. {scenario['name']}")
    
    print("\n" + "-" * 80)
    print("Running all scenarios...")
    print("-" * 80)
    
    results = []
    for scenario in scenarios:
        result = demo_scenario(
            scenario["bus_no"],
            scenario["direction"],
            scenario["lat"],
            scenario["lon"],
            scenario["name"]
        )
        if result:
            results.append(result)
        time.sleep(2)  # Brief pause between requests
    
    # Summary
    if results:
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        
        action_counts = {}
        for result in results:
            action = result['action']
            action_counts[action] = action_counts.get(action, 0) + 1
        
        print("\nAction Distribution:")
        for action, count in action_counts.items():
            print(f"  {action.replace('_', ' ').title()}: {count}")
        
        print(f"\nTotal scenarios tested: {len(results)}")
        print("\n" + "=" * 80)
    
    print("\n✅ Demo completed!")
    print("\nTo use the system:")
    print("  1. Start the backend: python backend/main.py")
    print("  2. Open frontend/index.html in a web browser")
    print("  3. Enter bus number, direction, and GPS coordinates")
    print("  4. Click 'Start' to begin receiving recommendations")


if __name__ == "__main__":
    main()
