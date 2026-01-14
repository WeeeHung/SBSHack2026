import requests
import json
import time
import os
import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
ONEMAP_TOKEN = os.getenv("ONEMAP_TOKEN")

# --- HELPER FUNCTIONS ---
def get_segment_geometry(start_coords, end_coords, token, use_bus_routing=True):
    """
    Fetches the route geometry between two points.
    Tries bus routing first, falls back to driving routing if unavailable.
    start_coords: "lat,lon"
    end_coords: "lat,lon"
    use_bus_routing: If True, try bus routing first, then fallback to drive
    """
    url = "https://www.onemap.gov.sg/api/public/routingsvc/route"
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    # Try bus routing first if requested
    if use_bus_routing:
        params = {
            "start": start_coords,
            "end": end_coords,
            "routeType": "pt",  # Public transport routing
            "mode": "BUS",      # Bus-specific routing
        }
        
        try:
            response = requests.get(url, params=params, headers=headers)
            data = response.json()
            
            if "route_geometry" in data and data['route_geometry']:
                # OneMap returns an encoded polyline string
                return data['route_geometry']
        except Exception as e:
            print(f"Bus routing error: {e}, falling back to drive routing")
    
    # Fallback to driving routing
    params = {
        "start": start_coords,
        "end": end_coords,
        "routeType": "drive",  # Driving route as fallback
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        
        if "route_geometry" in data:
            # OneMap returns an encoded polyline string
            return data['route_geometry']
        else:
            return None
    except Exception as e:
        print(f"Routing error: {e}")
        return None

# --- MAIN EXECUTION (Continuing from previous step) ---

# 1. Load the bus route data from CSV
csv_path = 'bus_route/output/bus_routes_147_190_960.csv'
if not os.path.exists(csv_path):
    print(f"Error: CSV file not found at {csv_path}")
    print("Please run retrieve_example_bus_route.py first to generate the data.")
    exit(1)

df_final = pd.read_csv(csv_path)
print(f"Loaded {len(df_final)} bus route records from {csv_path}")

# 2. Get Authentication Token
# Use existing token if available, otherwise generate new one with email/password
if ONEMAP_TOKEN:
    token = ONEMAP_TOKEN
    print("Using existing OneMap token from environment.")
else:
    print("Error: ONEMAP_TOKEN must be set in environment variables.")
    quit()

print("OneMap Token retrieved successfully.")

# We will store the detailed path here
detailed_route_segments = []

# Iterate through each specific bus service and direction
# We group by Service and Direction so we don't draw a line from Bus 147 to Bus 190
grouped = df_final.groupby(['ServiceNo', 'Direction'])

for name, group in grouped:
    service, direction = name
    print(f"Processing Service {service} (Direction {direction})...")
    
    # Ensure stops are in correct order
    stops = group.sort_values('StopSequence').reset_index(drop=True)
    
    # Loop through stops to create pairs (Stop N -> Stop N+1)
    for i in range(len(stops) - 1):
        start_node = stops.iloc[i]
        end_node = stops.iloc[i+1]
        
        start_str = f"{start_node['Latitude']},{start_node['Longitude']}"
        end_str = f"{end_node['Latitude']},{end_node['Longitude']}"
        
        # Fetch geometry
        geometry_string = get_segment_geometry(start_str, end_str, token)
        
        if geometry_string:
            # Decode the polyline into actual lat/lon list if needed
            # Note: Would need polyline library for decoding: polyline.decode(geometry_string)
            
            detailed_route_segments.append({
                'ServiceNo': service,
                'Direction': direction,
                'FromStop': start_node['BusStopCode'],
                'ToStop': end_node['BusStopCode'],
                'SequenceOrder': i,
                'Geometry': geometry_string # Encoded string is smaller to save
            })
        
        # Rate limiting (OneMap is usually generous, but be safe)
        time.sleep(0.2)

# Convert to DataFrame and Save
df_geometry = pd.DataFrame(detailed_route_segments)
output_path = 'bus_route/output/bus_route_geometry_onemap.csv'
os.makedirs(os.path.dirname(output_path), exist_ok=True)
df_geometry.to_csv(output_path, index=False)
print(f"Geometry data saved to {output_path}!")
