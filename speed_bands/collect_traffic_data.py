"""
Collect Traffic Speed Band data from LTA DataMall API
Calls API every 2 minutes for 2 hours and saves to JSON
"""
import os
import json
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# LTA DataMall API base URL (v4 endpoint)
BASE_URL = "https://datamall2.mytransport.sg/ltaodataservice/v4"

# Configuration
COLLECTION_DURATION_HOURS = 2
INTERVAL_MINUTES = 2
OUTPUT_FILE = "traffic_speed_data.json"


def get_traffic_speed_bands():
    """
    Fetch traffic speed band data from LTA DataMall API
    
    Returns:
        dict: API response containing traffic speed band information
    """
    # Get API credentials from environment variables
    account_key = os.getenv("LTA_DATAMALL")
    
    if not account_key:
        raise ValueError(
            "LTA_DATAMALL not found in environment variables. "
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


def load_existing_data(filename):
    """Load existing data from JSON file if it exists"""
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: {filename} exists but is not valid JSON. Starting fresh.")
            return {}
    return {}


def save_data(data, filename):
    """Save data to JSON file"""
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)


def process_and_append_data(api_response, existing_data, timestamp):
    """
    Process API response and append to existing data structure
    
    Format: {LinkID: [{speedband, minspeed, maxspeed, start coord, end coord, timestamp}]}
    """
    if "value" not in api_response:
        print("Warning: No 'value' key in API response")
        return existing_data
    
    speed_bands = api_response["value"]
    
    for band in speed_bands:
        link_id = band.get('LinkID')
        if not link_id:
            continue
        
        # Convert LinkID to string for JSON key consistency
        link_id_str = str(link_id)
        
        # Initialize array if LinkID doesn't exist
        if link_id_str not in existing_data:
            existing_data[link_id_str] = []
        
        # Create data entry
        entry = {
            "speedband": band.get('SpeedBand'),
            "minspeed": band.get('MinimumSpeed'),
            "maxspeed": band.get('MaximumSpeed'),
            "start_coord": [band.get('StartLat'), band.get('StartLon')],
            "end_coord": [band.get('EndLat'), band.get('EndLon')],
            "timestamp": timestamp
        }
        
        # Append to array for this LinkID
        existing_data[link_id_str].append(entry)
    
    return existing_data


def main():
    """Main function to collect traffic speed band data"""
    print("=" * 60)
    print("LTA DataMall Traffic Speed Band Data Collection")
    print("=" * 60)
    print(f"Duration: {COLLECTION_DURATION_HOURS} hours")
    print(f"Interval: {INTERVAL_MINUTES} minutes")
    print(f"Output file: {OUTPUT_FILE}")
    print("=" * 60)
    
    # Load existing data if file exists
    data = load_existing_data(OUTPUT_FILE)
    print(f"Loaded {len(data)} existing LinkIDs from {OUTPUT_FILE}")
    print()
    
    # Calculate total iterations
    total_iterations = (COLLECTION_DURATION_HOURS * 60) // INTERVAL_MINUTES
    interval_seconds = INTERVAL_MINUTES * 60
    
    print(f"Starting data collection...")
    print(f"Total iterations: {total_iterations}")
    print(f"Interval: {INTERVAL_MINUTES} minutes ({interval_seconds} seconds)")
    print()
    
    start_time = time.time()
    end_time = start_time + (COLLECTION_DURATION_HOURS * 3600)
    
    iteration = 0
    
    try:
        while time.time() < end_time:
            iteration += 1
            current_time = datetime.now()
            timestamp = current_time.isoformat()
            
            print(f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Iteration {iteration}/{total_iterations}")
            print("  Fetching data from API...")
            
            try:
                # Fetch data from API
                api_response = get_traffic_speed_bands()
                
                # Process and append data
                data = process_and_append_data(api_response, data, timestamp)
                
                # Save to file after each collection
                save_data(data, OUTPUT_FILE)
                
                if "value" in api_response:
                    num_records = len(api_response["value"])
                    print(f"  ✓ Collected {num_records} records")
                    print(f"  ✓ Total unique LinkIDs: {len(data)}")
                else:
                    print("  ⚠ No data in API response")
                
            except Exception as e:
                print(f"  ✗ Error during collection: {e}")
                print("  Continuing to next iteration...")
            
            # Calculate time remaining
            elapsed = time.time() - start_time
            remaining = end_time - time.time()
            
            if remaining > 0:
                remaining_minutes = int(remaining // 60)
                remaining_seconds = int(remaining % 60)
                print(f"  Time remaining: {remaining_minutes}m {remaining_seconds}s")
                print()
                
                # Wait for next interval (except on last iteration)
                if time.time() + interval_seconds < end_time:
                    print(f"  Waiting {INTERVAL_MINUTES} minutes until next collection...")
                    print()
                    time.sleep(interval_seconds)
            else:
                break
        
        print("=" * 60)
        print("Data collection completed!")
        print(f"Total iterations: {iteration}")
        print(f"Total unique LinkIDs: {len(data)}")
        print(f"Data saved to: {OUTPUT_FILE}")
        print("=" * 60)
        
        # Calculate total entries
        total_entries = sum(len(entries) for entries in data.values())
        print(f"Total data entries: {total_entries}")
        
    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("Collection interrupted by user")
        print(f"Saving current data to {OUTPUT_FILE}...")
        save_data(data, OUTPUT_FILE)
        print(f"Data saved. Total unique LinkIDs: {len(data)}")
        print("=" * 60)
    
    except Exception as e:
        print(f"\nError: {e}")
        print(f"Saving current data to {OUTPUT_FILE}...")
        save_data(data, OUTPUT_FILE)
        raise


if __name__ == "__main__":
    main()
