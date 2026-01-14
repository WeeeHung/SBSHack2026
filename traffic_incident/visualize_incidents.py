"""
Visualize Traffic Incidents on a map
Shows all current traffic incidents with their types and messages
"""
import json
import os
import folium
from folium import plugins
from collections import defaultdict

# Configuration
INPUT_FILE = os.path.join("traffic_incident/data", "traffic_incidents.json")
OUTPUT_FILE = os.path.join("traffic_incident/data", "traffic_incidents_map.html")

# Color mapping for different incident types
INCIDENT_COLORS = {
    "Accident": "red",
    "Roadwork": "orange",
    "Vehicle breakdown": "blue",
    "Weather": "lightblue",
    "Obstacle": "purple",
    "Road Block": "darkred",
    "Heavy Traffic": "yellow",
    "Miscellaneous": "gray",
    "Diversion": "green",
    "Unattended Vehicle": "pink",
    "Fire": "darkred",
    "Plant Failure": "brown",
    "Reverse Flow": "cyan"
}


def load_incidents_data(filename):
    """Load traffic incidents data from JSON file"""
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Data file '{filename}' not found. Run fetch_traffic_incidents.py first.")
    
    with open(filename, 'r') as f:
        data = json.load(f)
    
    # Handle both old format (direct dict with 'value') and new format (with metadata)
    if isinstance(data, dict) and "data" in data:
        # New format with metadata
        return data["data"].get("value", [])
    elif isinstance(data, dict) and "value" in data:
        # Direct API response format
        return data["value"]
    else:
        # Assume it's a list
        return data if isinstance(data, list) else []


def create_incidents_map(incidents, output_file):
    """
    Create a Folium map showing all traffic incidents
    """
    if not incidents:
        print("No incidents to visualize")
        return
    
    # Calculate center of map (average of all incident locations)
    latitudes = [float(incident.get("Latitude", 0)) for incident in incidents if incident.get("Latitude")]
    longitudes = [float(incident.get("Longitude", 0)) for incident in incidents if incident.get("Longitude")]
    
    if not latitudes or not longitudes:
        print("No valid coordinates found in incidents data")
        return
    
    # Use Singapore's approximate center if we have valid coordinates
    center_lat = sum(latitudes) / len(latitudes) if latitudes else 1.3521
    center_lon = sum(longitudes) / len(longitudes) if longitudes else 103.8198
    
    # Create base map centered on Singapore
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        tiles='OpenStreetMap'
    )
    
    # Group incidents by type for legend
    incidents_by_type = defaultdict(list)
    
    # Add markers for each incident
    for incident in incidents:
        lat = incident.get("Latitude")
        lon = incident.get("Longitude")
        incident_type = incident.get("Type", "Unknown")
        message = incident.get("Message", "No description")
        
        if lat is None or lon is None:
            continue
        
        try:
            lat = float(lat)
            lon = float(lon)
        except (ValueError, TypeError):
            continue
        
        # Get color for this incident type
        color = INCIDENT_COLORS.get(incident_type, "gray")
        
        # Create popup text
        popup_text = f"""
        <div style="width: 250px;">
            <h4 style="margin: 5px 0; color: {color};">{incident_type}</h4>
            <p style="margin: 5px 0;"><strong>Message:</strong></p>
            <p style="margin: 5px 0; font-size: 12px;">{message}</p>
            <p style="margin: 5px 0; font-size: 10px; color: #666;">
                Location: {lat:.6f}, {lon:.6f}
            </p>
        </div>
        """
        
        # Add marker
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_text, max_width=300),
            tooltip=f"{incident_type}: {message[:50]}...",
            icon=folium.Icon(color=color, icon='exclamation-triangle', prefix='fa')
        ).add_to(m)
        
        incidents_by_type[incident_type].append(incident)
    
    # Add legend
    legend_html = """
    <div style="position: fixed; 
                bottom: 50px; right: 50px; width: 200px; height: auto; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <h4 style="margin-top: 0;">Incident Types</h4>
    """
    
    for incident_type, color in sorted(INCIDENT_COLORS.items()):
        count = len(incidents_by_type.get(incident_type, []))
        if count > 0:
            legend_html += f"""
            <p style="margin: 5px 0;">
                <i class="fa fa-circle" style="color: {color}"></i> 
                {incident_type}: {count}
            </p>
            """
    
    legend_html += "</div>"
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Add fullscreen button
    plugins.Fullscreen().add_to(m)
    
    # Save map
    m.save(output_file)
    print(f"Map saved to: {output_file}")
    print(f"Total incidents visualized: {len(incidents)}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("Incident Summary")
    print("=" * 60)
    for incident_type in sorted(incidents_by_type.keys()):
        count = len(incidents_by_type[incident_type])
        print(f"{incident_type}: {count}")


def main():
    """Main function to visualize traffic incidents"""
    print("=" * 60)
    print("Traffic Incidents Visualization")
    print("=" * 60)
    
    try:
        # Load data
        print(f"Loading data from {INPUT_FILE}...")
        incidents = load_incidents_data(INPUT_FILE)
        print(f"Loaded {len(incidents)} incidents")
        
        if not incidents:
            print("No incidents found in the data file.")
            return
        
        # Create map
        print("\nCreating map visualization...")
        create_incidents_map(incidents, OUTPUT_FILE)
        
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
