"""
Fetch Traffic Incidents data from LTA DataMall API
Returns incidents currently happening on the roads, such as
Accidents, Vehicle Breakdowns, Road Blocks, Traffic Diversions etc.
Update Frequency: 2 minutes – whenever there are updates
"""
import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# LTA DataMall API endpoint for Traffic Incidents
API_URL = "https://datamall2.mytransport.sg/ltaodataservice/TrafficIncidents"

# Output directory
OUTPUT_DIR = "traffic_incident/data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "traffic_incidents.json")


def get_traffic_incidents():
    """
    Fetch traffic incidents data from LTA DataMall API
    
    Returns:
        dict: API response containing traffic incidents information
    """
    # Get API credentials from environment variables
    account_key = os.getenv("LTA_DATAMALL")
    
    if not account_key:
        raise ValueError(
            "LTA_DATAMALL not found in environment variables. "
            "Please set it in your .env file or environment."
        )
    
    # Headers required by LTA DataMall API
    headers = {
        "AccountKey": account_key,
        "accept": "application/json"
    }
    
    try:
        # Make API request
        response = requests.get(API_URL, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        # Parse JSON response
        data = response.json()
        
        return data
    
    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        raise


def save_incidents_data(data, filename):
    """Save traffic incidents data to JSON file with timestamp"""
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
    
    # Add metadata
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "count": len(data.get("value", [])) if isinstance(data, dict) and "value" in data else 0,
        "data": data
    }
    
    with open(filename, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"Data saved to: {filename}")


def main():
    """Main function to fetch traffic incidents data"""
    print("=" * 60)
    print("LTA DataMall Traffic Incidents Data Fetch")
    print("=" * 60)
    print(f"API URL: {API_URL}")
    print(f"Output file: {OUTPUT_FILE}")
    print("=" * 60)
    
    try:
        print("Fetching traffic incidents from API...")
        api_response = get_traffic_incidents()
        
        # Check if response has expected structure
        if isinstance(api_response, dict) and "value" in api_response:
            incidents = api_response["value"]
            print(f"✓ Successfully fetched {len(incidents)} traffic incidents")
            
            # Display summary by incident type
            if incidents:
                type_counts = {}
                for incident in incidents:
                    incident_type = incident.get("Type", "Unknown")
                    type_counts[incident_type] = type_counts.get(incident_type, 0) + 1
                
                print("\nIncident Summary by Type:")
                for incident_type, count in sorted(type_counts.items()):
                    print(f"  {incident_type}: {count}")
        else:
            print("⚠ Unexpected API response structure")
            print(f"Response keys: {list(api_response.keys()) if isinstance(api_response, dict) else 'Not a dict'}")
        
        # Save data to file
        save_incidents_data(api_response, OUTPUT_FILE)
        
        print("\n" + "=" * 60)
        print("Data fetch completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


if __name__ == "__main__":
    main()
