import requests
import pandas as pd
import time
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
API_KEY = os.getenv("LTA_DATAMALL")

# Example services
# Route 147 (City/Traffic heavy), Route 190 (Highway/Speed heavy), and Route 960 (Long haul).
TARGET_SERVICES = ['147', '190', '960']

# API Endpoints
DATAMALL_BUS_ROUTES = "https://datamall2.mytransport.sg/ltaodataservice/BusRoutes"
DATAMALL_BUS_STOPS = "https://datamall2.mytransport.sg/ltaodataservice/BusStops"

headers = {
    'AccountKey': API_KEY,
    'accept': 'application/json'
}

def fetch_all_data(url):
    """
    LTA API returns data in batches of 500. 
    This loops until all data is retrieved.
    """
    results = []
    skip = 0
    while True:
        # LTA uses $skip to paginate
        req_url = f"{url}?$skip={skip}"
        print(f"Fetching {url} (Skip: {skip})...")
        
        try:
            response = requests.get(req_url, headers=headers)
            if response.status_code != 200:
                print(f"Error: {response.status_code}")
                print(f"Response: {response.text}")
                break
                
            data = response.json()
            values = data.get('value', [])
            
            if not values:
                break
                
            results.extend(values)
            skip += 500
            
            # Respect API rate limits (optional but good practice)
            time.sleep(0.1) 
            
        except Exception as e:
            print(f"Exception occurred: {e}")
            break
            
    return pd.DataFrame(results)

# --- MAIN EXECUTION ---

print("--- Step 1: Fetching Bus Routes ---")
# 1. Get ALL bus route definitions (ServiceNo, Direction, StopSequence, BusStopCode)
df_routes_all = fetch_all_data(DATAMALL_BUS_ROUTES)

if df_routes_all.empty:
    print("ERROR: No data retrieved from Bus Routes API. Please check your API key and endpoint.")
    exit(1)

# Filter for only the 3 buses we care about
df_target_routes = df_routes_all[df_routes_all['ServiceNo'].isin(TARGET_SERVICES)].copy()
print(f"Found {len(df_target_routes)} route points for services {TARGET_SERVICES}")

print("\n--- Step 2: Fetching Bus Stop Coordinates ---")
# 2. Get ALL bus stop details (BusStopCode, Latitude, Longitude, Description)
# Note: We fetch all because checking individual stops one by one is slower.
df_stops_all = fetch_all_data(DATAMALL_BUS_STOPS)

if df_stops_all.empty:
    print("ERROR: No data retrieved from Bus Stops API. Please check your API key and endpoint.")
    exit(1)

# --- Step 3: Merging Data ---
print("\n--- Step 3: Merging Data ---")

# Merge route info with stop coordinates
df_final = pd.merge(
    df_target_routes,
    df_stops_all[['BusStopCode', 'Latitude', 'Longitude', 'Description', 'RoadName']],
    on='BusStopCode',
    how='left'
)

# Sort strictly by Service, Direction, and Sequence to ensure the path is correct
df_final = df_final.sort_values(by=['ServiceNo', 'Direction', 'StopSequence'])

# Remove first/last bus timing columns
timing_columns = ['WD_FirstBus', 'WD_LastBus', 'SAT_FirstBus', 'SAT_LastBus', 'SUN_FirstBus', 'SUN_LastBus']
df_final = df_final.drop(columns=[col for col in timing_columns if col in df_final.columns])

# --- Step 4: Export ---
output_filename = 'bus_route/output/bus_routes_147_190_960.csv'
# Create output directory if it doesn't exist
os.makedirs(os.path.dirname(output_filename), exist_ok=True)
df_final.to_csv(output_filename, index=False)

print(f"\nSuccess! Data saved to {output_filename}")
print(df_final.head())