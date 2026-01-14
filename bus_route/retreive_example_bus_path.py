import requests
import json
import time
import polyline 
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
ONEMAP_EMAIL = os.getenv("ONEMAP_EMAIL")
ONEMAP_PASSWORD = os.getenv("ONEMAP_PASSWORD")

# --- HELPER FUNCTIONS ---

def get_onemap_token(email, password):
    """
    Authenticates with OneMap to get an access token.
    Token is valid for 3 days.
    """
    url = "https://www.onemap.gov.sg/api/auth/post/getToken"
    payload = {
        "email": email,
        "password": password
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()['access_token']
    except Exception as e:
        print(f"Error getting token: {e}")
        return None

def get_segment_geometry(start_coords, end_coords, token):
    """
    Fetches the driving route geometry between two points.
    start_coords: "lat,lon"
    end_coords: "lat,lon"
    """
    url = "https://www.onemap.gov.sg/api/public/routingsvc/route"
    
    params = {
        "start": start_coords,
        "end": end_coords,
        "routeType": "drive", # Bus follows road logic
        "token": token
    }
    
    try:
        response = requests.get(url, params=params)
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

# 1. Get Authentication Token
token = get_onemap_token(ONEMAP_EMAIL, ONEMAP_PASSWORD)

if token:
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
                # decoded_path = polyline.decode(geometry_string)
                
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
    df_geometry.to_csv('bus_route_geometry_onemap.csv', index=False)
    print("Geometry data saved!")

else:
    print("Failed to authenticate with OneMap.")