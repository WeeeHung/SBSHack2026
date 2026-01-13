"""
Test script for LTA DataMall Traffic Speed Band API
"""
import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# LTA DataMall API base URL (v4 endpoint)
BASE_URL = "https://datamall2.mytransport.sg/ltaodataservice/v4"

def get_road_category_name(category):
    """Convert road category number to descriptive name"""
    categories = {
        1: "Expressways",
        2: "Major Arterial Roads",
        3: "Arterial Roads",
        4: "Minor Arterial Roads",
        5: "Small Roads",
        6: "Slip Roads",
        8: "Short Tunnels"
    }
    return categories.get(category, f"Unknown ({category})")


def get_speed_band_description(speed_band):
    """Convert speed band number to speed range description"""
    descriptions = {
        1: "0-9 km/h",
        2: "10-19 km/h",
        3: "20-29 km/h",
        4: "30-39 km/h",
        5: "40-49 km/h",
        6: "50-59 km/h",
        7: "60-69 km/h",
        8: "70+ km/h"
    }
    return descriptions.get(speed_band, f"Unknown ({speed_band})")


def get_traffic_speed_bands():
    """
    Fetch traffic speed band data from LTA DataMall API
    
    Returns:
        dict: API response containing traffic speed band information
    """
    # Get API credentials from environment variables
    account_key = os.getenv("LTA_ACCOUNT_KEY")
    
    if not account_key:
        raise ValueError(
            "LTA_ACCOUNT_KEY not found in environment variables. "
            "Please set it in your .env file or environment."
        )
    
    # API endpoint for Traffic Speed Bands
    endpoint = f"{BASE_URL}/TrafficSpeedBands"
    
    # Headers required by LTA DataMall API
    headers = {
        "AccountKey": account_key,
        "accept": "application/json"
    }
    
    try:
        # Make API request
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        # Parse JSON response
        data = response.json()
        
        return data
    
    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        raise


def main():
    """Main function to test the Traffic Speed Band API"""
    print("Testing LTA DataMall Traffic Speed Band API...")
    print("-" * 50)
    
    try:
        # Fetch traffic speed band data
        result = get_traffic_speed_bands()
        
        # Display results
        if "value" in result:
            speed_bands = result["value"]
            print(f"\nFound {len(speed_bands)} traffic speed band records\n")
            
            # Display first few records as sample
            for i, band in enumerate(speed_bands[495:], 1):
                print(f"Record {i}:")
                print(f"  LinkID: {band.get('LinkID', 'N/A')}")
                print(f"  RoadName: {band.get('RoadName', 'N/A')}")
                
                road_category = band.get('RoadCategory')
                if road_category:
                    print(f"  RoadCategory: {road_category} ({get_road_category_name(road_category)})")
                else:
                    print(f"  RoadCategory: N/A")
                
                speed_band = band.get('SpeedBand')
                if speed_band:
                    print(f"  SpeedBand: {speed_band} ({get_speed_band_description(speed_band)})")
                else:
                    print(f"  SpeedBand: N/A")
                
                print(f"  MinimumSpeed: {band.get('MinimumSpeed', 'N/A')} km/h")
                print(f"  MaximumSpeed: {band.get('MaximumSpeed', 'N/A')} km/h")
                
                # Coordinates
                print(f"  Start Coordinates: ({band.get('StartLat', 'N/A')}, {band.get('StartLon', 'N/A')})")
                print(f"  End Coordinates: ({band.get('EndLat', 'N/A')}, {band.get('EndLon', 'N/A')})")
                print()
            
            if len(speed_bands) > 5:
                print(f"... and {len(speed_bands) - 5} more records")
        else:
            print("Response structure:")
            print(result)
            
    except ValueError as e:
        print(f"Configuration Error: {e}")
        print("\nPlease create a .env file with your LTA_ACCOUNT_KEY:")
        print("LTA_ACCOUNT_KEY=your_account_key_here")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
