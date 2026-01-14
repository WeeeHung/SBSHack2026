import requests
import json
import time
import os
import pandas as pd

# --- HELPER FUNCTIONS ---
def get_segment_geometry_osrm(start_coords, end_coords):
    """
    Fetches route geometry using OSRM (free, auto-snaps to roads).
    start_coords: "lat,lon"
    end_coords: "lat,lon"
    """
    # OSRM uses lon,lat order (opposite of OneMap)
    start_lat, start_lon = [x.strip() for x in start_coords.split(',')]
    end_lat, end_lon = [x.strip() for x in end_coords.split(',')]
    
    url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}"
    params = {
        "overview": "full",      # Get full route geometry
        "geometries": "polyline" # Return encoded polyline (same format as OneMap)
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") == "Ok" and data.get("routes"):
            return data["routes"][0]["geometry"]
        else:
            print(f"OSRM routing error: {data.get('code', 'Unknown')}")
            return None
    except Exception as e:
        print(f"OSRM request error: {e}")
        return None

# --- MAIN EXECUTION ---

# 1. Load the bus route data from CSV
csv_path = 'bus_route/output/bus_routes_147_190_960.csv'
if not os.path.exists(csv_path):
    print(f"Error: CSV file not found at {csv_path}")
    print("Please run retrieve_example_bus_route.py first to generate the data.")
    exit(1)

df_final = pd.read_csv(csv_path)
print(f"Loaded {len(df_final)} bus route records from {csv_path}")

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
        
        # Fetch geometry using OSRM
        geometry_string = get_segment_geometry_osrm(start_str, end_str)
        
        if geometry_string:
            detailed_route_segments.append({
                'ServiceNo': service,
                'Direction': direction,
                'FromStop': start_node['BusStopCode'],
                'ToStop': end_node['BusStopCode'],
                'SequenceOrder': i,
                'Geometry': geometry_string # Encoded string is smaller to save
            })
        
        # Rate limiting (be respectful to public OSRM server)
        time.sleep(0.2)

# Convert to DataFrame and Save
df_geometry = pd.DataFrame(detailed_route_segments)
output_path = 'bus_route/output/bus_route_geometry_osrm.csv'
os.makedirs(os.path.dirname(output_path), exist_ok=True)
df_geometry.to_csv(output_path, index=False)
print(f"Geometry data saved to {output_path}!")
