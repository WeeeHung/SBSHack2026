import pandas as pd
import folium
import polyline
import os
import argparse
from collections import defaultdict
from shapely.geometry import LineString

# --- CONFIGURATION ---
ONEMAP_CSV_PATH = 'bus_route/output/bus_route_geometry_onemap.csv'
OSRM_CSV_PATH = 'bus_route/output/bus_route_geometry_osrm.csv'
BUS_ROUTES_CSV = 'bus_route/output/bus_routes_147_190_960.csv'
OUTPUT_HTML = 'bus_route/output/bus_routes_map.html'

# Singapore center coordinates
SINGAPORE_CENTER = [1.3521, 103.8198]

# Color palette for different routes
# Each ServiceNo-Direction combination gets a unique color
COLORS = [
    '#FF0000',  # Red
    '#0000FF',  # Blue
    '#00FF00',  # Green
    '#FF00FF',  # Magenta
    '#00FFFF',  # Cyan
    '#FFFF00',  # Yellow
    '#FFA500',  # Orange
    '#800080',  # Purple
    '#FF1493',  # Deep Pink
    '#00CED1',  # Dark Turquoise
    '#32CD32',  # Lime Green
    '#FF4500',  # Orange Red
    '#1E90FF',  # Dodger Blue
    '#FF69B4',  # Hot Pink
    '#20B2AA',  # Light Sea Green
    '#9370DB',  # Medium Purple
]

def get_route_color(service_no, direction, color_map):
    """Get a unique color for each ServiceNo-Direction combination"""
    key = f"{service_no}_{direction}"
    if key not in color_map:
        color_map[key] = COLORS[len(color_map) % len(COLORS)]
    return color_map[key]

def decode_geometry(encoded_polyline):
    """Decode an encoded polyline string to list of [lat, lon] coordinates"""
    try:
        # polyline.decode returns [(lat, lon), ...]
        # We need to convert to [[lat, lon], ...] for folium
        decoded = polyline.decode(encoded_polyline)
        return [[lat, lon] for lat, lon in decoded]
    except Exception as e:
        print(f"Error decoding polyline: {e}")
        return []

def deduplicate_points(coords, tolerance=0.00001):
    """
    Remove duplicate or very close consecutive points.
    tolerance: Distance threshold in degrees (approximately 1 meter ≈ 0.00001 degrees)
    """
    if len(coords) < 2:
        return coords
    
    deduplicated = [coords[0]]  # Always keep first point
    
    for i in range(1, len(coords)):
        prev_point = deduplicated[-1]
        curr_point = coords[i]
        
        # Calculate distance between points
        lat_diff = abs(curr_point[0] - prev_point[0])
        lon_diff = abs(curr_point[1] - prev_point[1])
        distance = (lat_diff ** 2 + lon_diff ** 2) ** 0.5
        
        # Only add point if it's far enough from previous point
        if distance > tolerance:
            deduplicated.append(curr_point)
    
    return deduplicated

def simplify_polyline(coords, tolerance=0.00001):
    """
    Simplify polyline using Douglas-Peucker algorithm via Shapely.
    tolerance: Simplification tolerance in degrees (approximately 1 meter ≈ 0.00001 degrees)
    """
    if len(coords) < 3:
        return coords
    
    try:
        # Create LineString from coordinates (note: Shapely uses (lon, lat) order)
        line = LineString([(lon, lat) for lat, lon in coords])
        
        # Simplify using Douglas-Peucker algorithm (simplify is a method on LineString)
        simplified_line = line.simplify(tolerance=tolerance, preserve_topology=True)
        
        # Convert back to [[lat, lon], ...] format
        # simplified_line.coords returns tuples of (lon, lat)
        simplified_coords = [[lat, lon] for lon, lat in simplified_line.coords]
        
        return simplified_coords
    except Exception as e:
        print(f"Error simplifying polyline: {e}")
        return coords

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Visualize bus routes from geometry data')
    parser.add_argument(
        '--source',
        choices=['onemap', 'osrm', 'auto'],
        default='auto',
        help='Source of geometry data: onemap, osrm, or auto (default: auto - tries osrm first, then onemap)'
    )
    parser.add_argument(
        '--csv',
        type=str,
        default=None,
        help='Custom path to geometry CSV file (overrides --source)'
    )
    args = parser.parse_args()
    
    # Determine which CSV file to use
    if args.csv:
        csv_path = args.csv
        if not os.path.exists(csv_path):
            print(f"Error: CSV file not found at {csv_path}")
            return
    elif args.source == 'onemap':
        csv_path = ONEMAP_CSV_PATH
    elif args.source == 'osrm':
        csv_path = OSRM_CSV_PATH
    else:  # auto
        # Try OSRM first, then fall back to OneMap
        if os.path.exists(OSRM_CSV_PATH):
            csv_path = OSRM_CSV_PATH
            print(f"Auto-detected: Using OSRM geometry data")
        elif os.path.exists(ONEMAP_CSV_PATH):
            csv_path = ONEMAP_CSV_PATH
            print(f"Auto-detected: Using OneMap geometry data")
        else:
            print(f"Error: No geometry CSV file found.")
            print(f"  Expected OSRM file at: {OSRM_CSV_PATH}")
            print(f"  Expected OneMap file at: {ONEMAP_CSV_PATH}")
            print(f"  Please run retreive_example_bus_path_osrm.py or retreive_example_bus_path_onemap.py first.")
            return
    
    # Check if CSV file exists
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        print("Please run retreive_example_bus_path_osrm.py or retreive_example_bus_path_onemap.py first to generate the geometry data.")
        return
    
    # Load the geometry data
    print(f"Loading geometry data from {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} route segments")
    
    # Load bus routes data to get bus stop locations
    bus_stops_df = None
    if os.path.exists(BUS_ROUTES_CSV):
        print(f"Loading bus stop data from {BUS_ROUTES_CSV}...")
        bus_stops_df = pd.read_csv(BUS_ROUTES_CSV)
        print(f"Loaded {len(bus_stops_df)} bus stop records")
    else:
        print(f"Warning: Bus routes CSV not found at {BUS_ROUTES_CSV}. Bus stops will not be displayed.")
    
    # Create a map centered on Singapore
    print("Creating map...")
    m = folium.Map(
        location=SINGAPORE_CENTER,
        zoom_start=11,
        tiles='OpenStreetMap'
    )
    
    # Group by ServiceNo and Direction to organize routes
    grouped = df.groupby(['ServiceNo', 'Direction'])
    
    # Color mapping for routes
    color_map = {}
    
    # Track route statistics
    route_stats = defaultdict(int)
    
    # Process each route
    for (service_no, direction), group in grouped:
        route_key = f"{service_no}_{direction}"
        color = get_route_color(service_no, direction, color_map)
        
        # Sort by sequence order to maintain route order
        sorted_group = group.sort_values('SequenceOrder')
        
        # Collect all coordinates for this route
        all_coordinates = []
        
        for idx, row in sorted_group.iterrows():
            geometry_str = row['Geometry']
            if pd.notna(geometry_str) and geometry_str:
                coords = decode_geometry(geometry_str)
                if coords:
                    all_coordinates.extend(coords)
                    route_stats[route_key] += len(coords)
        
        # Apply deduplication and simplification to smooth the route
        if all_coordinates:
            original_count = len(all_coordinates)
            
            # Step 1: Deduplicate points at segment boundaries
            all_coordinates = deduplicate_points(all_coordinates, tolerance=0.00001)
            after_dedup_count = len(all_coordinates)
            
            # Step 2: Simplify polyline to reduce jaggedness
            all_coordinates = simplify_polyline(all_coordinates, tolerance=0.00001)
            after_simplify_count = len(all_coordinates)
            
            print(f"    Route smoothing: {original_count} -> {after_dedup_count} (dedup) -> {after_simplify_count} (simplified) points")
        
        # Draw the route as a polyline
        if all_coordinates:
            route_name = f"Bus {service_no} - Direction {direction}"
            
            folium.PolyLine(
                locations=all_coordinates,
                color=color,
                weight=4,
                opacity=0.8,
                popup=folium.Popup(route_name, max_width=200),
                tooltip=route_name
            ).add_to(m)
            
            print(f"  Added {route_name}: {len(all_coordinates)} points, color: {color}")
        
        # Add bus stop markers for this route
        if bus_stops_df is not None:
            route_stops = bus_stops_df[
                (bus_stops_df['ServiceNo'] == service_no) & 
                (bus_stops_df['Direction'] == direction)
            ].sort_values('StopSequence')
            
            stop_count = 0
            for idx, stop in route_stops.iterrows():
                if pd.notna(stop['Latitude']) and pd.notna(stop['Longitude']):
                    # Create popup with bus stop information
                    popup_text = f"""
                    <b>Bus {service_no} - Direction {direction}</b><br>
                    <b>Stop {stop['StopSequence']}: {stop.get('Description', 'N/A')}</b><br>
                    Code: {stop['BusStopCode']}<br>
                    Road: {stop.get('RoadName', 'N/A')}
                    """
                    
                    # Add marker with route color
                    folium.CircleMarker(
                        location=[stop['Latitude'], stop['Longitude']],
                        radius=5,
                        popup=folium.Popup(popup_text, max_width=250),
                        tooltip=f"Bus {service_no} - {stop.get('Description', stop['BusStopCode'])}",
                        color=color,
                        fillColor=color,
                        fillOpacity=0.8,
                        weight=2
                    ).add_to(m)
                    stop_count += 1
            
            if stop_count > 0:
                print(f"    Added {stop_count} bus stop markers")
    
    # Add a legend
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 200px; height: auto; 
                background-color: white; z-index:9999; font-size:14px;
                border:2px solid grey; border-radius:5px; padding: 10px;
                ">
    <h4 style="margin-top:0; margin-bottom:10px;">Bus Routes</h4>
    '''
    
    for key, color in sorted(color_map.items()):
        service, direction = key.split('_')
        legend_html += f'''
        <p style="margin: 5px 0;">
            <i class="fa fa-circle" style="color:{color}; font-size:16px;"></i>
            Bus {service} Dir {direction}
        </p>
        '''
    
    legend_html += '</div>'
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Save the map
    output_path = OUTPUT_HTML
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    m.save(output_path)
    
    print(f"\nMap saved to {output_path}!")
    print(f"\nRoute Statistics:")
    for route, point_count in sorted(route_stats.items()):
        print(f"  {route}: {point_count} coordinate points")
    print(f"\nTotal routes visualized: {len(color_map)}")

if __name__ == "__main__":
    main()
