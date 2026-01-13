"""
Create an interactive time-lapse heatmap of traffic speed data on Singapore map
Uses folium with TimestampedGeoJson to show traffic evolution over time
"""
import folium
from folium.plugins import TimestampedGeoJson
import json
import os
from datetime import datetime
from collections import defaultdict


def load_traffic_data(filename):
    """Load traffic data from JSON file"""
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Data file '{filename}' not found. Run collect_traffic_data.py first.")
    
    with open(filename, 'r') as f:
        data = json.load(f)
    
    return data


def get_color(speedband):
    """
    Traffic Light Color Logic
    Band 1 (0-10) = Black/Dark Red (Stuck)
    Band 2 (10-20) = Red (Congested)
    Band 3-4 = Orange/Yellow (Slow)
    Band 5+ = Green (Moving)
    """
    if speedband == 1:
        return '#000000'  # Black for dead stops
    elif speedband == 2:
        return '#FF0000'  # Red
    elif speedband <= 4:
        return '#FFA500'  # Orange
    else:
        return '#008000'  # Green


def calculate_period(timestamps):
    """
    Calculate the average time period between timestamps
    Returns ISO 8601 duration string (e.g., 'PT2M' for 2 minutes)
    """
    if len(timestamps) < 2:
        return 'PT2M'  # Default to 2 minutes
    
    # Parse timestamps and calculate differences
    parsed_times = []
    for ts in timestamps:
        try:
            if isinstance(ts, str):
                # Handle ISO format with microseconds
                if 'T' in ts:
                    date_part, time_part = ts.split('T')
                    if '.' in time_part:
                        time_part, microsecond = time_part.split('.')
                        microsecond = int(microsecond.ljust(6, '0')[:6])
                    else:
                        microsecond = 0
                    year, month, day = map(int, date_part.split('-'))
                    hour, minute, second = map(int, time_part.split(':'))
                    parsed_times.append(datetime(year, month, day, hour, minute, second, microsecond))
        except (ValueError, AttributeError):
            continue
    
    if len(parsed_times) < 2:
        return 'PT2M'
    
    # Calculate average difference
    differences = []
    for i in range(1, len(parsed_times)):
        diff = (parsed_times[i] - parsed_times[i-1]).total_seconds()
        if diff > 0:
            differences.append(diff)
    
    if not differences:
        return 'PT2M'
    
    avg_seconds = sum(differences) / len(differences)
    
    # Convert to ISO 8601 duration format
    if avg_seconds < 60:
        return f'PT{int(avg_seconds)}S'
    elif avg_seconds < 3600:
        minutes = int(avg_seconds / 60)
        return f'PT{minutes}M'
    else:
        hours = int(avg_seconds / 3600)
        minutes = int((avg_seconds % 3600) / 60)
        if minutes > 0:
            return f'PT{hours}H{minutes}M'
        return f'PT{hours}H'


def prepare_geojson_features(data):
    """
    Prepare data for TimestampedGeoJson
    Returns GeoJSON feature collection and calculated period
    
    This function ensures lines persist across timestamps by using the last known
    value for each link when no new data is available, preventing flashing.
    """
    # Step 1: Collect all timestamps and organize data by link
    all_timestamps_set = set()
    link_data = {}  # link_id -> {timestamp -> observation}
    link_coords = {}  # link_id -> (start_coord, end_coord)
    
    for link_id, observations in data.items():
        link_data[link_id] = {}
        
        for obs in observations:
            # Extract and validate coordinates (only need to do this once per link)
            try:
                start_lat = float(obs['start_coord'][0])
                start_lon = float(obs['start_coord'][1])
                end_lat = float(obs['end_coord'][0])
                end_lon = float(obs['end_coord'][1])
                
                # Store coordinates for this link (use first valid observation)
                if link_id not in link_coords:
                    link_coords[link_id] = ([start_lon, start_lat], [end_lon, end_lat])
            except (ValueError, KeyError, IndexError) as e:
                print(f"Warning: Skipping observation with invalid coordinates for link {link_id}: {e}")
                continue
            
            # Extract timestamp
            timestamp = obs.get('timestamp')
            if not timestamp:
                continue
            
            all_timestamps_set.add(timestamp)
            link_data[link_id][timestamp] = obs
    
    # Step 2: Sort all timestamps
    all_timestamps = sorted(list(all_timestamps_set))
    
    # Step 3: For each link, create features only when speedband value changes
    # This reduces the number of features and prevents flashing
    # Each feature will persist until the next change
    features = []
    
    for link_id in link_data.keys():
        if link_id not in link_coords:
            continue  # Skip links with no valid coordinates
        
        start_coord, end_coord = link_coords[link_id]
        last_known_obs = None
        last_speedband = None
        feature_start_time = None
        
        for i, timestamp in enumerate(all_timestamps):
            # Get observation for this timestamp, or use last known
            obs = link_data[link_id].get(timestamp)
            if obs is None:
                # No data for this timestamp - use last known value
                if last_known_obs is None:
                    continue  # Skip if we haven't seen any data for this link yet
                obs = last_known_obs
            else:
                # Update last known observation
                last_known_obs = obs
            
            # Extract speed information
            speedband = obs.get('speedband', 1)
            minspeed = obs.get('minspeed', '0')
            maxspeed = obs.get('maxspeed', '0')
            
            # Check if this is a new value or first timestamp
            is_first = (feature_start_time is None)
            is_last = (i == len(all_timestamps) - 1)
            value_changed = (speedband != last_speedband)
            
            if is_first:
                # Initialize first feature
                feature_start_time = timestamp
                last_speedband = speedband
            elif value_changed or is_last:
                # Create feature for the previous value (from start to current timestamp)
                prev_obs = link_data[link_id].get(feature_start_time)
                if prev_obs is None and last_known_obs is not None:
                    prev_obs = last_known_obs
                
                if prev_obs is not None:
                    prev_speedband = prev_obs.get('speedband', 1)
                    prev_minspeed = prev_obs.get('minspeed', '0')
                    prev_maxspeed = prev_obs.get('maxspeed', '0')
                    prev_color = get_color(prev_speedband)
                    
                    # Create feature spanning from start time to current time
                    features.append({
                        'type': 'Feature',
                        'geometry': {
                            'type': 'LineString',
                            'coordinates': [start_coord, end_coord]
                        },
                        'properties': {
                            'times': [feature_start_time, timestamp],  # Span from start to end
                            'style': {
                                'color': prev_color,
                                'weight': 10,
                                'opacity': 0.9
                            },
                            'popup': f"Link: {link_id} | Speed: {prev_minspeed}-{prev_maxspeed} km/h | Band: {prev_speedband}"
                        }
                    })
                
                # Start new feature with new value
                feature_start_time = timestamp
                last_speedband = speedband
                
                # If this is the last timestamp, also create a final feature
                if is_last and value_changed:
                    color = get_color(speedband)
                    features.append({
                        'type': 'Feature',
                        'geometry': {
                            'type': 'LineString',
                            'coordinates': [start_coord, end_coord]
                        },
                        'properties': {
                            'times': [timestamp, timestamp],
                            'style': {
                                'color': color,
                                'weight': 10,
                                'opacity': 0.9
                            },
                            'popup': f"Link: {link_id} | Speed: {minspeed}-{maxspeed} km/h | Band: {speedband}"
                        }
                    })
    
    geojson_layer = {
        'type': 'FeatureCollection',
        'features': features
    }
    
    # Calculate period from timestamps
    period = calculate_period(all_timestamps)
    
    return geojson_layer, period


def calculate_map_center(data):
    """
    Calculate the center point of the map from all coordinates
    """
    all_lats = []
    all_lons = []
    
    for link_id, observations in data.items():
        for obs in observations:
            try:
                start_lat = float(obs['start_coord'][0])
                start_lon = float(obs['start_coord'][1])
                end_lat = float(obs['end_coord'][0])
                end_lon = float(obs['end_coord'][1])
                
                all_lats.extend([start_lat, end_lat])
                all_lons.extend([start_lon, end_lon])
            except (ValueError, KeyError, IndexError):
                continue
    
    if all_lats and all_lons:
        center_lat = sum(all_lats) / len(all_lats)
        center_lon = sum(all_lons) / len(all_lons)
        return [center_lat, center_lon]
    
    # Default to Singapore center if no valid coordinates
    return [1.29206, 103.838305]


def create_timelapse_map(data, output_file="traffic_timelapse.html"):
    """
    Create an interactive time-lapse map of traffic data
    """
    print("Preparing GeoJSON features...")
    geojson_layer, period = prepare_geojson_features(data)
    
    print(f"Created {len(geojson_layer['features'])} features")
    print(f"Calculated period: {period}")
    
    if not geojson_layer['features']:
        print("Error: No valid features to display")
        return
    
    # Calculate map center
    center = calculate_map_center(data)
    print(f"Map center: {center}")
    
    # Initialize Map (Singapore Center)
    # Using OpenStreetMap tiles as default (OneMap requires API key)
    m = folium.Map(
        location=center,
        zoom_start=15,
        tiles='OpenStreetMap'
    )
    
    # Alternative: Use OneMap tiles if available (uncomment and configure if needed)
    # m = folium.Map(
    #     location=center,
    #     zoom_start=15,
    #     tiles='https://maps-{s}.onemap.sg/v3/Default/{z}/{x}/{y}.png',
    #     attr='&copy; OneMap | &copy; contributors',
    #     overlay=False
    # )
    
    # Add the Time Slider Player
    print("Adding TimestampedGeoJson layer...")
    if geojson_layer['features']:
        sample_feature = geojson_layer['features'][0]
        print(f"Sample feature times: {sample_feature['properties'].get('times', 'N/A')}")
        print(f"Sample feature style: {sample_feature['properties'].get('style', 'N/A')}")
        print(f"Sample feature geometry type: {sample_feature['geometry']['type']}")
        print(f"Sample feature coordinates: {sample_feature['geometry']['coordinates']}")
    
    # Add TimestampedGeoJson with proper styling for lines
    # Since we create features that span time ranges, duration should be long enough
    # to keep features visible until they're replaced by new ones
    TimestampedGeoJson(
        geojson_layer,
        period=period,  # Dynamically calculated period
        duration=None,  # Keep all features visible - prevents flashing
        add_last_point=False,  # Don't add point markers, only lines
        auto_play=False,  # Don't auto-play on load
        loop=False,
        time_slider_drag_update=True,
        transition_time=50,  # Very fast transition to minimize flashing
        date_options='YYYY-MM-DD HH:mm:ss'  # Date format for display
    ).add_to(m)
    
    # Add a legend - positioned at top-right to avoid overlap with time slider
    # Also add custom CSS to ensure time slider doesn't overlap
    custom_css = '''
    <style>
        .leaflet-control-container .leaflet-timedimension-control {
            bottom: 10px !important;
            left: 10px !important;
        }
    </style>
    '''
    m.get_root().html.add_child(folium.Element(custom_css))
    
    legend_html = '''
    <div style="position: fixed; 
                top: 10px; right: 10px; width: 220px; height: 140px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:13px; padding: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
    <h4 style="margin-top:0; margin-bottom:8px; font-size:14px;">Traffic Speed Bands</h4>
    <p style="margin:4px 0;"><i class="fa fa-circle" style="color:#000000"></i> Band 1: 0-10 km/h (Stuck)</p>
    <p style="margin:4px 0;"><i class="fa fa-circle" style="color:#FF0000"></i> Band 2: 10-20 km/h (Congested)</p>
    <p style="margin:4px 0;"><i class="fa fa-circle" style="color:#FFA500"></i> Band 3-4: 20-40 km/h (Slow)</p>
    <p style="margin:4px 0;"><i class="fa fa-circle" style="color:#008000"></i> Band 5+: 40+ km/h (Moving)</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Save map
    m.save(output_file)
    print(f"\n{'='*60}")
    print(f"Timelapse map generated: {output_file}")
    print(f"{'='*60}")
    print(f"Open this file in a web browser to view the interactive map.")
    print(f"The map includes a time slider at the bottom to play/pause the animation.")
    
    return output_file


def main():
    """Main function to create time-lapse map"""
    print("=" * 60)
    print("Singapore Traffic Time-Lapse Heatmap Generator")
    print("=" * 60)
    
    input_file = "traffic_speed_data.json"
    output_file = "traffic_timelapse.html"
    
    try:
        # Load data
        print(f"\nLoading data from {input_file}...")
        data = load_traffic_data(input_file)
        print(f"Loaded data for {len(data)} road links")
        
        # Count total observations
        total_obs = sum(len(observations) for observations in data.values())
        print(f"Total observations: {total_obs}")
        
        # Create time-lapse map
        print("\n" + "=" * 60)
        print("Creating time-lapse map...")
        print("=" * 60)
        create_timelapse_map(data, output_file)
        
        print("\nMap creation complete!")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
