"""
Test script for LTA DataMall Traffic Speed Band API
"""
import os
import json
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


def get_traffic_speed_bands(skip=0):
    """
    Fetch traffic speed band data from LTA DataMall API
    
    Args:
        skip: Number of records to skip (for pagination)
    
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
    
    # Add $skip parameter if needed
    params = {}
    if skip > 0:
        params['$skip'] = skip
    
    # Headers required by LTA DataMall API
    headers = {
        "AccountKey": account_key,
        "accept": "application/json"
    }
    
    try:
        # Make API request
        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        # Parse JSON response
        data = response.json()
        
        return data
    
    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        raise


def main():
    """Main function to fetch all links from Traffic Speed Band API"""
    print("=" * 60)
    print("LTA DataMall Traffic Speed Band API - Fetch All Links")
    print("=" * 60)
    
    output_file = "links.json"
    all_links = []
    skip = 0
    page = 1
    max_records_per_page = 500
    
    try:
        print(f"\nStarting to fetch all links...")
        print(f"Output file: {output_file}\n")
        
        while True:
            print(f"Page {page}: Fetching records starting from {skip}...", end=" ")
            
            # Fetch traffic speed band data
            result = get_traffic_speed_bands(skip=skip)
            
            if "value" not in result:
                print("No 'value' key in response. Stopping.")
                break
            
            speed_bands = result["value"]
            num_records = len(speed_bands)
            
            if num_records == 0:
                print("No records returned. Reached end of data.")
                break
            
            # Add all links to our collection
            all_links.extend(speed_bands)
            print(f"✓ Retrieved {num_records} records (Total: {len(all_links)})")
            
            # Check if we've reached the end (less than max records means last page)
            if num_records < max_records_per_page:
                print(f"\nReached end of data (got {num_records} < {max_records_per_page} records)")
                break
            
            # Increment skip for next iteration
            skip += max_records_per_page
            page += 1
        
        # Save all links to JSON file
        print(f"\n{'=' * 60}")
        print(f"Saving {len(all_links)} total links to {output_file}...")
        
        with open(output_file, 'w') as f:
            json.dump(all_links, f, indent=2)
        
        print(f"✓ Successfully saved {len(all_links)} links to {output_file}")
        print(f"{'=' * 60}")
        
        # Display summary statistics
        if all_links:
            print(f"\nSummary:")
            print(f"  Total links collected: {len(all_links)}")
            
            # Count unique LinkIDs
            unique_link_ids = set(link.get('LinkID') for link in all_links if link.get('LinkID'))
            print(f"  Unique LinkIDs: {len(unique_link_ids)}")
            
            # Display first record as sample
            print(f"\nSample record (first link):")
            first_link = all_links[0]
            print(f"  LinkID: {first_link.get('LinkID', 'N/A')}")
            print(f"  RoadName: {first_link.get('RoadName', 'N/A')}")
            
            road_category = first_link.get('RoadCategory')
            if road_category:
                print(f"  RoadCategory: {road_category} ({get_road_category_name(road_category)})")
            
            speed_band = first_link.get('SpeedBand')
            if speed_band:
                print(f"  SpeedBand: {speed_band} ({get_speed_band_description(speed_band)})")
            
            print(f"  Start Coordinates: ({first_link.get('StartLat', 'N/A')}, {first_link.get('StartLon', 'N/A')})")
            print(f"  End Coordinates: ({first_link.get('EndLat', 'N/A')}, {first_link.get('EndLon', 'N/A')})")
            
    except ValueError as e:
        print(f"Configuration Error: {e}")
        print("\nPlease create a .env file with your LTA_ACCOUNT_KEY:")
        print("LTA_ACCOUNT_KEY=your_account_key_here")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
