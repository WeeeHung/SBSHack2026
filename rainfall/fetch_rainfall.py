"""
Fetch Rainfall data from data.gov.sg API
Returns precipitation readings at weather-station level, updated every five minutes.
Data from National Environment Agency (NEA)
Update Frequency: Every 5 minutes
"""
import os
import json
import requests
from datetime import datetime

# data.gov.sg API endpoint for Rainfall
API_URL = "https://api.data.gov.sg/v1/environment/rainfall"

# Output directory
OUTPUT_DIR = "rainfall/data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "rainfall_data.json")


def get_rainfall_data():
    """
    Fetch rainfall data from data.gov.sg API
    
    Returns:
        dict: API response containing rainfall information
    """
    try:
        # Make API request (no authentication required for data.gov.sg)
        response = requests.get(API_URL)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        # Parse JSON response
        data = response.json()
        
        return data
    
    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        raise


def save_rainfall_data(data, filename):
    """Save rainfall data to JSON file with timestamp"""
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
    
    # Add metadata
    items = data.get("items", [])
    total_readings = sum(len(item.get("readings", [])) for item in items)
    
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "items_count": len(items),
        "total_readings": total_readings,
        "data": data
    }
    
    with open(filename, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"Data saved to: {filename}")


def main():
    """Main function to fetch rainfall data"""
    print("=" * 60)
    print("data.gov.sg Rainfall Data Fetch")
    print("=" * 60)
    print(f"API URL: {API_URL}")
    print(f"Output file: {OUTPUT_FILE}")
    print("=" * 60)
    
    try:
        print("Fetching rainfall data from API...")
        api_response = get_rainfall_data()
        
        # Check if response has expected structure
        if isinstance(api_response, dict) and "items" in api_response:
            items = api_response["items"]
            print(f"✓ Successfully fetched {len(items)} time period(s)")
            
            # Display summary
            if items:
                for item in items:
                    timestamp = item.get("timestamp", "Unknown")
                    readings = item.get("readings", [])
                    print(f"\nTimestamp: {timestamp}")
                    print(f"  Number of station readings: {len(readings)}")
                    
                    # Display statistics if readings available
                    if readings:
                        values = [r.get("value", 0) for r in readings if r.get("value") is not None]
                        if values:
                            print(f"  Rainfall range: {min(values):.2f} - {max(values):.2f} mm")
                            print(f"  Average rainfall: {sum(values)/len(values):.2f} mm")
                            print(f"  Stations with rainfall (>0): {sum(1 for v in values if v > 0)}")
        else:
            print("⚠ Unexpected API response structure")
            print(f"Response keys: {list(api_response.keys()) if isinstance(api_response, dict) else 'Not a dict'}")
        
        # Save data to file
        save_rainfall_data(api_response, OUTPUT_FILE)
        
        print("\n" + "=" * 60)
        print("Data fetch completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


if __name__ == "__main__":
    main()
