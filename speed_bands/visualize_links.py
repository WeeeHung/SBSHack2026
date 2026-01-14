"""
Visualize all road links from links.json on a Singapore map using folium
Shows which roads are covered by the LTA Traffic Speed Band API
"""
import folium
import json
import os


def load_links(filename):
    """Load links data from JSON file"""
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Links file '{filename}' not found. Run test_traffic_speed_band.py first.")
    
    with open(filename, 'r') as f:
        links = json.load(f)
    
    return links


def get_road_category_color(road_category):
    """
    Get color based on road category
    """
    # category_colors = {
    #     "1": "#FF0000",  # Red - Expressways
    #     "2": "#FF8C00",  # Dark Orange - Major Arterial Roads
    #     "3": "#FFA500",  # Orange - Arterial Roads
    #     "4": "#FFD700",  # Gold - Minor Arterial Roads
    #     "5": "#90EE90",  # Light Green - Small Roads
    #     "6": "#87CEEB",  # Sky Blue - Slip Roads
    #     "8": "#9370DB"   # Medium Purple - Short Tunnels
    # }
    # return category_colors.get(str(road_category), "#808080")  # Gray for unknown
    return "#000000"


def get_road_category_name(category):
    """Convert road category number to descriptive name"""
    categories = {
        "1": "Expressways",
        "2": "Major Arterial Roads",
        "3": "Arterial Roads",
        "4": "Minor Arterial Roads",
        "5": "Small Roads",
        "6": "Slip Roads",
        "8": "Short Tunnels"
    }
    return categories.get(str(category), f"Unknown ({category})")


def calculate_map_center(links):
    """
    Calculate the center point of the map from all coordinates
    """
    all_lats = []
    all_lons = []
    
    for link in links:
        try:
            start_lat = float(link.get('StartLat', 0))
            start_lon = float(link.get('StartLon', 0))
            end_lat = float(link.get('EndLat', 0))
            end_lon = float(link.get('EndLon', 0))
            
            if start_lat and start_lon:
                all_lats.append(start_lat)
                all_lons.append(start_lon)
            if end_lat and end_lon:
                all_lats.append(end_lat)
                all_lons.append(end_lon)
        except (ValueError, TypeError):
            continue
    
    if all_lats and all_lons:
        center_lat = sum(all_lats) / len(all_lats)
        center_lon = sum(all_lons) / len(all_lons)
        return [center_lat, center_lon]
    
    # Default to Singapore center if no valid coordinates
    return [1.29206, 103.838305]


def create_links_map(links, output_file="links_map.html"):
    """
    Create an interactive map showing all road links
    """
    print(f"Processing {len(links)} links...")
    
    # Calculate map center
    center = calculate_map_center(links)
    print(f"Map center: {center}")
    
    # Initialize Map (Singapore Center)
    m = folium.Map(
        location=center,
        zoom_start=12,
        tiles='OpenStreetMap'
    )
    
    # Count links by category for statistics
    category_counts = {}
    valid_links = 0
    invalid_links = 0
    
    # Add each link as a line
    for link in links:
        try:
            start_lat = float(link.get('StartLat', 0))
            start_lon = float(link.get('StartLon', 0))
            end_lat = float(link.get('EndLat', 0))
            end_lon = float(link.get('EndLon', 0))
            
            # Skip if coordinates are invalid
            if not all([start_lat, start_lon, end_lat, end_lon]):
                invalid_links += 1
                continue
            
            # Get road category and color
            road_category = link.get('RoadCategory', 'Unknown')
            color = get_road_category_color(road_category)
            
            # Count by category
            category_str = str(road_category)
            category_counts[category_str] = category_counts.get(category_str, 0) + 1
            
            # Get link information for popup
            link_id = link.get('LinkID', 'N/A')
            road_name = link.get('RoadName', 'N/A')
            speed_band = link.get('SpeedBand', 'N/A')
            min_speed = link.get('MinimumSpeed', 'N/A')
            max_speed = link.get('MaximumSpeed', 'N/A')
            
            # Create popup text
            popup_text = f"""
            <b>Link ID:</b> {link_id}<br>
            <b>Road Name:</b> {road_name}<br>
            <b>Category:</b> {get_road_category_name(road_category)}<br>
            <b>Speed Band:</b> {speed_band}<br>
            <b>Speed:</b> {min_speed}-{max_speed} km/h
            """
            
            # Create line from start to end coordinates
            folium.PolyLine(
                locations=[[start_lat, start_lon], [end_lat, end_lon]],
                color=color,
                weight=3,
                opacity=0.7,
                popup=folium.Popup(popup_text, max_width=300)
            ).add_to(m)
            
            valid_links += 1
            
        except (ValueError, TypeError, KeyError) as e:
            invalid_links += 1
            continue
    
    print(f"✓ Added {valid_links} valid links to map")
    if invalid_links > 0:
        print(f"⚠ Skipped {invalid_links} links with invalid coordinates")
    
    # Add legend
    legend_html = '''
    <div style="position: fixed; 
                top: 10px; right: 10px; width: 280px; height: 280px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:13px; padding: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                overflow-y: auto; max-height: 80vh;">
    <h4 style="margin-top:0; margin-bottom:10px; font-size:14px; font-weight:bold;">Road Categories</h4>
    '''
    
    # Add legend items for each category found
    for category in sorted(category_counts.keys()):
        count = category_counts[category]
        color = get_road_category_color(category)
        name = get_road_category_name(category)
        legend_html += f'''
    <p style="margin:6px 0;">
        <span style="display:inline-block; width:20px; height:12px; background-color:{color}; border:1px solid #333; margin-right:8px; vertical-align:middle;"></span>
        {name} ({count} links)
    </p>
    '''
    
    legend_html += '''
    <hr style="margin:10px 0;">
    <p style="margin:4px 0; font-size:11px; color:#666;">
        Total: ''' + str(valid_links) + ''' links
    </p>
    </div>
    '''
    
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Save map
    m.save(output_file)
    print(f"\n{'='*60}")
    print(f"Map generated: {output_file}")
    print(f"{'='*60}")
    print(f"Open this file in a web browser to view the interactive map.")
    print(f"\nStatistics:")
    print(f"  Valid links: {valid_links}")
    print(f"  Invalid links: {invalid_links}")
    print(f"  Road categories: {len(category_counts)}")
    
    return output_file


def main():
    """Main function to visualize links on map"""
    print("=" * 60)
    print("Singapore Road Links Visualizer")
    print("=" * 60)
    
    input_file = "speed_bands/data/links_147_1.json"
    output_file = "speed_bands/data/links_map_147_1.html"
    
    try:
        # Load links
        print(f"\nLoading links from {input_file}...")
        links = load_links(input_file)
        print(f"Loaded {len(links)} links")
        
        # Create map
        print("\n" + "=" * 60)
        print("Creating map...")
        print("=" * 60)
        create_links_map(links, output_file)
        
        print("\nMap creation complete!")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
