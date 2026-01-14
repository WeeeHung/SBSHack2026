"""
Visualize ordered links from links_by_geometry JSON files.

Shows the route progression with color-coded links based on order,
and optionally displays connectivity (inbound/outbound links).
"""
import json
import os
import argparse
import folium
from folium import plugins
import math

# Singapore center coordinates
SINGAPORE_CENTER = [1.3521, 103.8198]


def load_route_data(json_path):
    """Load route data from JSON file"""
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON file not found: {json_path}")
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    return data


def calculate_map_center(ordered_links):
    """Calculate map center from link coordinates"""
    all_lats = []
    all_lons = []
    
    for link in ordered_links:
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
    
    return SINGAPORE_CENTER


def get_color_by_order(order, total_links):
    """
    Get color based on link order (gradient from blue to red).
    Uses HSV color space for smooth gradient.
    """
    if total_links <= 1:
        return '#0000FF'  # Blue
    
    # Normalize order to 0-1
    normalized = order / (total_links - 1)
    
    # Create gradient from blue (hue=240) to red (hue=0)
    # HSV: hue goes from 240 (blue) to 0 (red) through purple
    hue = 240 * (1 - normalized)
    saturation = 1.0
    value = 1.0
    
    # Convert HSV to RGB
    import colorsys
    rgb = colorsys.hsv_to_rgb(hue/360, saturation, value)
    hex_color = '#{:02x}{:02x}{:02x}'.format(
        int(rgb[0] * 255),
        int(rgb[1] * 255),
        int(rgb[2] * 255)
    )
    
    return hex_color


def get_color_by_speed_band(speed_band):
    """Get color based on speed band"""
    speed_colors = {
        1: '#FF0000',  # Red - Very slow (0-9 km/h)
        2: '#FF4500',  # Orange Red - Slow (10-19 km/h)
        3: '#FFA500',  # Orange - Moderate (20-29 km/h)
        4: '#FFD700',  # Gold - Medium (30-39 km/h)
        5: '#ADFF2F',  # Green Yellow - Fast (40-49 km/h)
        6: '#32CD32',  # Lime Green - Faster (50-59 km/h)
        7: '#00FF00',  # Green - Fast (60-69 km/h)
        8: '#00CED1',  # Dark Turquoise - Very Fast (70+ km/h)
    }
    return speed_colors.get(speed_band, '#808080')  # Gray for unknown


def create_link_popup(link):
    """Create HTML popup content for a link"""
    popup_html = f"""
    <div style="font-family: Arial, sans-serif;">
        <h4 style="margin: 0 0 10px 0;">Link {link.get('LinkID', 'N/A')}</h4>
        <table style="border-collapse: collapse; width: 100%;">
            <tr>
                <td style="padding: 2px 5px; font-weight: bold;">Road:</td>
                <td style="padding: 2px 5px;">{link.get('RoadName', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 2px 5px; font-weight: bold;">Order:</td>
                <td style="padding: 2px 5px;">{link.get('order', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 2px 5px; font-weight: bold;">Distance:</td>
                <td style="padding: 2px 5px;">{link.get('distance_along_route', 0):.4f}</td>
            </tr>
            <tr>
                <td style="padding: 2px 5px; font-weight: bold;">Speed Band:</td>
                <td style="padding: 2px 5px;">{link.get('SpeedBand', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 2px 5px; font-weight: bold;">Speed:</td>
                <td style="padding: 2px 5px;">{link.get('MinimumSpeed', 'N/A')}-{link.get('MaximumSpeed', 'N/A')} km/h</td>
            </tr>
            <tr>
                <td style="padding: 2px 5px; font-weight: bold;">Inbound:</td>
                <td style="padding: 2px 5px;">{len(link.get('inbound_link_ids', []))} links</td>
            </tr>
            <tr>
                <td style="padding: 2px 5px; font-weight: bold;">Outbound:</td>
                <td style="padding: 2px 5px;">{len(link.get('outbound_link_ids', []))} links</td>
            </tr>
            <tr>
                <td style="padding: 2px 5px; font-weight: bold;">Next:</td>
                <td style="padding: 2px 5px;">{', '.join(link.get('next_link_ids', [])) or 'None'}</td>
            </tr>
        </table>
    </div>
    """
    return folium.Popup(popup_html, max_width=300)


def visualize_ordered_links(json_path, output_path=None, color_by='order', show_connectivity=False):
    """
    Visualize ordered links on a map.
    
    Args:
        json_path: Path to links_by_geometry JSON file
        output_path: Output HTML file path (default: same as JSON with .html extension)
        color_by: 'order' or 'speed' - how to color the links
        show_connectivity: Whether to show inbound/outbound link connections
    """
    # Load data
    print(f"Loading route data from {json_path}...")
    route_data = load_route_data(json_path)
    
    service_no = route_data.get('ServiceNo')
    direction = route_data.get('Direction')
    ordered_links = route_data.get('ordered_links', [])
    
    print(f"Route: Bus {service_no} - Direction {direction}")
    print(f"Total links: {len(ordered_links)}")
    
    if not ordered_links:
        print("No links to visualize")
        return
    
    # Calculate map center
    center = calculate_map_center(ordered_links)
    
    # Create map
    print("Creating map...")
    m = folium.Map(
        location=center,
        zoom_start=13,
        tiles='OpenStreetMap'
    )
    
    # Add fullscreen button
    plugins.Fullscreen().add_to(m)
    
    # Create feature groups for different layers
    links_layer = folium.FeatureGroup(name='Route Links')
    connectivity_layer = folium.FeatureGroup(name='Connectivity', show=False)
    
    # Draw links
    print("Drawing links...")
    for link in ordered_links:
        try:
            start_lat = float(link['StartLat'])
            start_lon = float(link['StartLon'])
            end_lat = float(link['EndLat'])
            end_lon = float(link['EndLon'])
            order = link.get('order', 0)
            
            # Choose color based on mode
            if color_by == 'order':
                color = get_color_by_order(order, len(ordered_links))
            elif color_by == 'speed':
                speed_band = link.get('SpeedBand', 1)
                color = get_color_by_speed_band(speed_band)
            else:
                color = '#0000FF'  # Default blue
            
            # Create polyline for the link
            folium.PolyLine(
                locations=[[start_lat, start_lon], [end_lat, end_lon]],
                color=color,
                weight=8,
                opacity=0.8,
                popup=create_link_popup(link),
                tooltip=f"Link {link.get('LinkID')} - Order {order}"
            ).add_to(links_layer)
            
            # Add start point marker
            folium.CircleMarker(
                location=[start_lat, start_lon],
                radius=3,
                color='green',
                fillColor='green',
                fillOpacity=0.8,
                weight=1,
                popup=f"Start: Link {link.get('LinkID')}"
            ).add_to(links_layer)
            
            # Add end point marker
            folium.CircleMarker(
                location=[end_lat, end_lon],
                radius=3,
                color='red',
                fillColor='red',
                fillOpacity=0.8,
                weight=1,
                popup=f"End: Link {link.get('LinkID')}"
            ).add_to(links_layer)
            
            # Show connectivity if requested
            if show_connectivity:
                # Draw inbound connections
                inbound_ids = link.get('inbound_link_ids', [])
                for inbound_id in inbound_ids:
                    if inbound_id in route_data.get('link_index', {}):
                        inbound_link = route_data['link_index'][inbound_id]
                        try:
                            inbound_end_lat = float(inbound_link['EndLat'])
                            inbound_end_lon = float(inbound_link['EndLon'])
                            
                            # Draw arrow from inbound end to current start
                            folium.PolyLine(
                                locations=[[inbound_end_lat, inbound_end_lon], [start_lat, start_lon]],
                                color='blue',
                                weight=2,
                                opacity=0.5,
                                dashArray='5, 5',
                                tooltip=f"Inbound: {inbound_id} → {link.get('LinkID')}"
                            ).add_to(connectivity_layer)
                        except (ValueError, KeyError):
                            continue
                
                # Draw outbound connections
                outbound_ids = link.get('outbound_link_ids', [])
                for outbound_id in outbound_ids:
                    if outbound_id in route_data.get('link_index', {}):
                        outbound_link = route_data['link_index'][outbound_id]
                        try:
                            outbound_start_lat = float(outbound_link['StartLat'])
                            outbound_start_lon = float(outbound_link['StartLon'])
                            
                            # Draw arrow from current end to outbound start
                            folium.PolyLine(
                                locations=[[end_lat, end_lon], [outbound_start_lat, outbound_start_lon]],
                                color='orange',
                                weight=2,
                                opacity=0.5,
                                dashArray='5, 5',
                                tooltip=f"Outbound: {link.get('LinkID')} → {outbound_id}"
                            ).add_to(connectivity_layer)
                        except (ValueError, KeyError):
                            continue
        
        except (ValueError, KeyError) as e:
            print(f"Error processing link {link.get('LinkID', 'unknown')}: {e}")
            continue
    
    # Add layers to map
    links_layer.add_to(m)
    if show_connectivity:
        connectivity_layer.add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Add legend
    legend_html = f'''
    <div style="position: fixed; 
                bottom: 50px; right: 50px; width: 200px; height: auto; 
                background-color: white; z-index:9999; font-size:12px;
                border:2px solid grey; border-radius:5px; padding: 10px;
                ">
    <h4 style="margin-top:0; margin-bottom:10px;">Bus {service_no} - Direction {direction}</h4>
    <p style="margin: 5px 0;"><b>Total Links:</b> {len(ordered_links)}</p>
    <p style="margin: 5px 0;"><b>Color By:</b> {color_by.title()}</p>
    <p style="margin: 5px 0;">
        <span style="background-color: green; width: 10px; height: 10px; display: inline-block; border-radius: 50%;"></span>
        Start Point
    </p>
    <p style="margin: 5px 0;">
        <span style="background-color: red; width: 10px; height: 10px; display: inline-block; border-radius: 50%;"></span>
        End Point
    </p>
    '''
    
    if show_connectivity:
        legend_html += '''
    <p style="margin: 5px 0;">
        <span style="color: blue; font-weight: bold;">---</span>
        Inbound Links
    </p>
    <p style="margin: 5px 0;">
        <span style="color: orange; font-weight: bold;">---</span>
        Outbound Links
    </p>
    '''
    
    legend_html += '</div>'
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Determine output path
    if output_path is None:
        base_name = os.path.splitext(json_path)[0]
        output_path = f"{base_name}_map.html"
    
    # Save map
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    m.save(output_path)
    
    print(f"\nMap saved to {output_path}!")
    print(f"Visualized {len(ordered_links)} links")


def main():
    parser = argparse.ArgumentParser(
        description='Visualize ordered links from links_by_geometry JSON files'
    )
    parser.add_argument(
        'json_file',
        type=str,
        help='Path to links_by_geometry JSON file'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output HTML file path (default: same as JSON with _map.html extension)'
    )
    parser.add_argument(
        '--color-by',
        choices=['order', 'speed'],
        default='order',
        help='How to color links: order (gradient) or speed (speed band) (default: order)'
    )
    parser.add_argument(
        '--show-connectivity',
        action='store_true',
        help='Show inbound/outbound link connections'
    )
    
    args = parser.parse_args()
    
    visualize_ordered_links(
        args.json_file,
        args.output,
        args.color_by,
        args.show_connectivity
    )


if __name__ == "__main__":
    main()
