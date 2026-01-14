"""
Visualize Rainfall data on a map
Shows all weather stations with rainfall readings, colored by intensity
"""
import json
import os
import folium
from folium import plugins

# Configuration
INPUT_FILE = os.path.join("rainfall/data", "rainfall_data.json")
OUTPUT_FILE = os.path.join("rainfall/data", "rainfall_map.html")


def get_color_for_rainfall(value):
    """
    Get color based on rainfall value (mm)
    Returns color from light blue (low) to dark blue/purple (high)
    """
    if value == 0:
        return '#e3f2fd'  # Very light blue (no rain)
    elif value < 0.5:
        return '#90caf9'  # Light blue (light rain)
    elif value < 1.0:
        return '#64b5f6'  # Medium-light blue
    elif value < 2.0:
        return '#42a5f5'  # Medium blue
    elif value < 5.0:
        return '#2196f3'  # Blue
    elif value < 10.0:
        return '#1e88e5'  # Medium-dark blue
    elif value < 20.0:
        return '#1565c0'  # Dark blue
    elif value < 50.0:
        return '#0d47a1'  # Very dark blue
    else:
        return '#4a148c'  # Purple (very heavy rain)


def get_icon_size_for_rainfall(value):
    """
    Get icon size based on rainfall value
    Returns size in pixels
    """
    if value == 0:
        return 6
    elif value < 1.0:
        return 8
    elif value < 5.0:
        return 10
    elif value < 10.0:
        return 12
    elif value < 20.0:
        return 14
    else:
        return 16


def load_rainfall_data(filename):
    """Load rainfall data from JSON file"""
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Data file '{filename}' not found. Run fetch_rainfall.py first.")
    
    with open(filename, 'r') as f:
        data = json.load(f)
    
    # Handle both direct API response and wrapped format
    if isinstance(data, dict) and "data" in data:
        # Wrapped format with metadata
        return data["data"]
    else:
        # Direct API response format
        return data


def create_rainfall_map(rainfall_data, output_file):
    """
    Create a Folium map showing all rainfall stations with their readings
    """
    metadata = rainfall_data.get("metadata", {})
    stations = metadata.get("stations", [])
    items = rainfall_data.get("items", [])
    
    if not stations:
        print("No station metadata found")
        return
    
    if not items:
        print("No rainfall readings found")
        return
    
    # Get the most recent readings (usually the first item)
    latest_item = items[0]
    readings = latest_item.get("readings", [])
    timestamp = latest_item.get("timestamp", "Unknown")
    
    # Create a dictionary mapping station_id to rainfall value
    rainfall_by_station = {r.get("station_id"): r.get("value", 0) for r in readings}
    
    # Calculate center of map (average of all station locations)
    latitudes = [s.get("location", {}).get("latitude", 0) for s in stations if s.get("location", {}).get("latitude")]
    longitudes = [s.get("location", {}).get("longitude", 0) for s in stations if s.get("location", {}).get("longitude")]
    
    if not latitudes or not longitudes:
        print("No valid coordinates found in station data")
        return
    
    # Use Singapore's approximate center
    center_lat = sum(latitudes) / len(latitudes) if latitudes else 1.3521
    center_lon = sum(longitudes) / len(longitudes) if longitudes else 103.8198
    
    # Create base map centered on Singapore
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        tiles='OpenStreetMap'
    )
    
    # Statistics for legend
    total_stations = len(stations)
    stations_with_readings = 0
    stations_with_rain = 0
    max_rainfall = 0
    total_rainfall = 0
    
    # Add markers for each station
    for station in stations:
        station_id = station.get("id")
        station_name = station.get("name", "Unknown")
        location = station.get("location", {})
        lat = location.get("latitude")
        lon = location.get("longitude")
        
        if lat is None or lon is None:
            continue
        
        try:
            lat = float(lat)
            lon = float(lon)
        except (ValueError, TypeError):
            continue
        
        # Get rainfall value for this station
        rainfall_value = rainfall_by_station.get(station_id, 0)
        
        # Update statistics
        if station_id in rainfall_by_station:
            stations_with_readings += 1
            if rainfall_value > 0:
                stations_with_rain += 1
            if rainfall_value > max_rainfall:
                max_rainfall = rainfall_value
            total_rainfall += rainfall_value
        
        # Get color and size based on rainfall
        color = get_color_for_rainfall(rainfall_value)
        icon_size = get_icon_size_for_rainfall(rainfall_value)
        
        # Create popup text
        rainfall_display = f"{rainfall_value:.2f} mm" if rainfall_value > 0 else "No rainfall"
        popup_text = f"""
        <div style="width: 250px;">
            <h4 style="margin: 5px 0;">{station_name}</h4>
            <p style="margin: 5px 0;"><strong>Station ID:</strong> {station_id}</p>
            <p style="margin: 5px 0;"><strong>Rainfall:</strong> {rainfall_display}</p>
            <p style="margin: 5px 0; font-size: 10px; color: #666;">
                Location: {lat:.6f}, {lon:.6f}
            </p>
        </div>
        """
        
        # Add circle marker (size represents intensity)
        folium.CircleMarker(
            location=[lat, lon],
            radius=icon_size,
            popup=folium.Popup(popup_text, max_width=300),
            tooltip=f"{station_name}: {rainfall_display}",
            color='white',
            weight=1,
            fillColor=color,
            fillOpacity=0.7
        ).add_to(m)
    
    # Add legend
    avg_rainfall = total_rainfall / stations_with_readings if stations_with_readings > 0 else 0
    
    legend_html = f"""
    <div style="position: fixed; 
                bottom: 50px; right: 50px; width: 220px; height: auto; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <h4 style="margin-top: 0;">Rainfall Intensity</h4>
    <p style="margin: 5px 0; font-size: 12px;"><strong>Timestamp:</strong><br>{timestamp}</p>
    <p style="margin: 5px 0; font-size: 11px;"><strong>Statistics:</strong></p>
    <p style="margin: 2px 0; font-size: 11px;">Total Stations: {total_stations}</p>
    <p style="margin: 2px 0; font-size: 11px;">Stations with Rain: {stations_with_rain}</p>
    <p style="margin: 2px 0; font-size: 11px;">Max Rainfall: {max_rainfall:.2f} mm</p>
    <p style="margin: 2px 0; font-size: 11px;">Avg Rainfall: {avg_rainfall:.2f} mm</p>
    <hr style="margin: 8px 0;">
    <p style="margin: 5px 0; font-size: 11px;"><strong>Color Scale (mm):</strong></p>
    <p style="margin: 2px 0; font-size: 10px;">
        <span style="color: #e3f2fd;">●</span> 0 (No rain)
    </p>
    <p style="margin: 2px 0; font-size: 10px;">
        <span style="color: #90caf9;">●</span> &lt; 0.5 (Light)
    </p>
    <p style="margin: 2px 0; font-size: 10px;">
        <span style="color: #42a5f5;">●</span> 1-2 (Moderate)
    </p>
    <p style="margin: 2px 0; font-size: 10px;">
        <span style="color: #2196f3;">●</span> 2-5 (Heavy)
    </p>
    <p style="margin: 2px 0; font-size: 10px;">
        <span style="color: #1565c0;">●</span> 5-20 (Very Heavy)
    </p>
    <p style="margin: 2px 0; font-size: 10px;">
        <span style="color: #4a148c;">●</span> &gt; 50 (Extreme)
    </p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Add fullscreen button
    plugins.Fullscreen().add_to(m)
    
    # Save map
    m.save(output_file)
    print(f"Map saved to: {output_file}")
    print(f"Total stations visualized: {total_stations}")
    print(f"Stations with rainfall data: {stations_with_readings}")
    print(f"Stations with rain (>0mm): {stations_with_rain}")
    print(f"Maximum rainfall: {max_rainfall:.2f} mm")
    print(f"Average rainfall: {avg_rainfall:.2f} mm")


def main():
    """Main function to visualize rainfall data"""
    print("=" * 60)
    print("Rainfall Data Visualization")
    print("=" * 60)
    
    try:
        # Load data
        print(f"Loading data from {INPUT_FILE}...")
        rainfall_data = load_rainfall_data(INPUT_FILE)
        print("Data loaded successfully")
        
        # Create map
        print("\nCreating map visualization...")
        create_rainfall_map(rainfall_data, OUTPUT_FILE)
        
        print("\n" + "=" * 60)
        print("Visualization complete!")
        print(f"Open {OUTPUT_FILE} in a web browser to view the map.")
        print("=" * 60)
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
