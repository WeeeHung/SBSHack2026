"""
Find road links that align with bus routes using geometry-based buffering.

For each bus route, this script:
1. Extracts route geometry from CSV (decoded polylines)
2. Finds links within a buffer distance of the route
3. Orders links along the route
4. Determines inbound/outbound/next links based on endpoint proximity
5. Outputs JSON files with ordered links and connectivity data
"""
import pandas as pd
import polyline
import json
import os
import argparse
import math
from shapely.geometry import LineString, Point
from shapely.ops import transform
import pyproj

# --- CONFIGURATION ---
ONEMAP_CSV_PATH = 'bus_route/output/bus_route_geometry_onemap.csv'
OSRM_CSV_PATH = 'bus_route/output/bus_route_geometry_osrm.csv'
LINKS_JSON_PATH = 'speed_bands/data/links.json'
OUTPUT_DIR = 'bus_route/output'
BUFFER_METERS = 5  # Buffer distance in meters

# Singapore approximate UTM zone (48N)
SINGAPORE_UTM = 'EPSG:32648'  # UTM Zone 48N
WGS84 = 'EPSG:4326'


def decode_geometry(encoded_polyline):
    """Decode an encoded polyline string to list of [lat, lon] coordinates"""
    try:
        # polyline.decode returns [(lat, lon), ...]
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
        
        # Simplify using Douglas-Peucker algorithm
        simplified_line = line.simplify(tolerance=tolerance, preserve_topology=True)
        
        # Convert back to [[lat, lon], ...] format
        simplified_coords = [[lat, lon] for lon, lat in simplified_line.coords]
        
        return simplified_coords
    except Exception as e:
        print(f"Error simplifying polyline: {e}")
        return coords


def get_route_linestring(df, service_no, direction):
    """
    Extract route coordinates as Shapely LineString object for a specific route.
    
    Args:
        df: DataFrame with geometry data
        service_no: Service number
        direction: Direction (1 or 2)
    
    Returns:
        Shapely LineString in (lon, lat) order, or None if no geometry found
    """
    route_df = df[(df['ServiceNo'] == service_no) & (df['Direction'] == direction)]
    
    if route_df.empty:
        return None
    
    # Sort by sequence order
    sorted_df = route_df.sort_values('SequenceOrder')
    
    # Collect all coordinates
    all_coordinates = []
    for idx, row in sorted_df.iterrows():
        geometry_str = row['Geometry']
        if pd.notna(geometry_str) and geometry_str:
            coords = decode_geometry(geometry_str)
            if coords:
                all_coordinates.extend(coords)
    
    if not all_coordinates:
        return None
    
    # Apply deduplication and simplification
    all_coordinates = deduplicate_points(all_coordinates, tolerance=0.00001)
    all_coordinates = simplify_polyline(all_coordinates, tolerance=0.00001)
    
    # Create LineString (Shapely uses lon, lat order)
    line = LineString([(lon, lat) for lat, lon in all_coordinates])
    
    return line


def create_link_linestring(link):
    """
    Create a Shapely LineString from a link dictionary.
    
    Args:
        link: Dictionary with StartLat, StartLon, EndLat, EndLon
    
    Returns:
        Shapely LineString in (lon, lat) order, or None if invalid
    """
    try:
        start_lat = float(link['StartLat'])
        start_lon = float(link['StartLon'])
        end_lat = float(link['EndLat'])
        end_lon = float(link['EndLon'])
        
        return LineString([(start_lon, start_lat), (end_lon, end_lat)])
    except (ValueError, KeyError) as e:
        return None


def find_links_in_buffer(route_linestring, all_links, buffer_meters):
    """
    Find links that fall within a buffer range of the route.
    
    Uses UTM projection for accurate meter-based buffering.
    
    Args:
        route_linestring: Shapely LineString of the route (lon, lat order, WGS84)
        all_links: List of link dictionaries
        buffer_meters: Buffer distance in meters
    
    Returns:
        List of links that intersect the buffered route
    """
    if route_linestring is None or route_linestring.is_empty:
        return []
    
    # Create projection transformers (using pyproj 3+ API)
    transformer_to_utm = pyproj.Transformer.from_crs(WGS84, SINGAPORE_UTM, always_xy=True)
    transformer_to_wgs84 = pyproj.Transformer.from_crs(SINGAPORE_UTM, WGS84, always_xy=True)
    
    # Transform route to UTM
    route_utm = transform(transformer_to_utm.transform, route_linestring)
    
    # Buffer in meters (UTM uses meters)
    buffered_route_utm = route_utm.buffer(buffer_meters)
    
    # Transform buffer back to WGS84 for intersection checks
    buffered_route = transform(transformer_to_wgs84.transform, buffered_route_utm)
    
    matching_links = []
    for link in all_links:
        link_line = create_link_linestring(link)
        if link_line is None:
            continue
        
        # Check if link intersects with buffered route
        if link_line.intersects(buffered_route):
            matching_links.append(link)
    
    return matching_links


def order_links_along_route(links, route_linestring):
    """
    Order links by their position along the route.
    
    Args:
        links: List of link dictionaries
        route_linestring: Shapely LineString of the route (lon, lat order)
    
    Returns:
        List of tuples: (link, distance_along_route, order_index)
    """
    if route_linestring is None or route_linestring.is_empty:
        return []
    
    link_positions = []
    
    for link in links:
        link_line = create_link_linestring(link)
        if link_line is None:
            continue
        
        # Get midpoint of the link
        midpoint = link_line.interpolate(0.5, normalized=True)
        
        # Project midpoint onto route and get distance along route
        # Find closest point on route to midpoint
        closest_point = route_linestring.interpolate(
            route_linestring.project(midpoint)
        )
        
        # Calculate distance along route from start
        distance_along = route_linestring.project(closest_point)
        
        link_positions.append((link, distance_along))
    
    # Sort by distance along route
    link_positions.sort(key=lambda x: x[1])
    
    # Return with order index
    ordered_links = []
    for order, (link, distance_along) in enumerate(link_positions):
        ordered_links.append((link, distance_along, order))
    
    return ordered_links


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points on Earth
    using the Haversine formula.
    
    Returns distance in meters.
    """
    # Earth radius in meters
    R = 6371000
    
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    # Haversine formula
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def points_match(lat1, lon1, lat2, lon2, buffer_meters):
    """
    Check if two points are within the buffer distance.
    
    Returns True if distance <= buffer_meters.
    """
    distance = haversine_distance(lat1, lon1, lat2, lon2)
    return distance <= buffer_meters


def find_inbound_links(current_link, all_links, buffer_meters):
    """
    Find links whose END point is within buffer of current link's START point.
    These are links that lead INTO the current link.
    
    Args:
        current_link: Link dictionary
        all_links: List of all link dictionaries
        buffer_meters: Buffer distance in meters
    
    Returns:
        List of link IDs that are inbound
    """
    try:
        current_start_lat = float(current_link['StartLat'])
        current_start_lon = float(current_link['StartLon'])
        current_link_id = current_link['LinkID']
    except (ValueError, KeyError):
        return []
    
    inbound_link_ids = []
    
    for link in all_links:
        if link['LinkID'] == current_link_id:
            continue
        
        try:
            link_end_lat = float(link['EndLat'])
            link_end_lon = float(link['EndLon'])
            
            # Check if link's end point is near current link's start point
            if points_match(current_start_lat, current_start_lon, 
                          link_end_lat, link_end_lon, buffer_meters):
                inbound_link_ids.append(link['LinkID'])
        except (ValueError, KeyError):
            continue
    
    return inbound_link_ids


def find_outbound_links(current_link, all_links, buffer_meters):
    """
    Find links whose START point is within buffer of current link's END point.
    These are links that lead OUT FROM the current link.
    
    Args:
        current_link: Link dictionary
        all_links: List of all link dictionaries
        buffer_meters: Buffer distance in meters
    
    Returns:
        List of link IDs that are outbound
    """
    try:
        current_end_lat = float(current_link['EndLat'])
        current_end_lon = float(current_link['EndLon'])
        current_link_id = current_link['LinkID']
    except (ValueError, KeyError):
        return []
    
    outbound_link_ids = []
    
    for link in all_links:
        if link['LinkID'] == current_link_id:
            continue
        
        try:
            link_start_lat = float(link['StartLat'])
            link_start_lon = float(link['StartLon'])
            
            # Check if link's start point is near current link's end point
            if points_match(current_end_lat, current_end_lon,
                          link_start_lat, link_start_lon, buffer_meters):
                outbound_link_ids.append(link['LinkID'])
        except (ValueError, KeyError):
            continue
    
    return outbound_link_ids


def find_next_links(current_order, ordered_links):
    """
    Find the next link(s) in the ordered sequence.
    
    Args:
        current_order: Order index of current link
        ordered_links: List of (link, distance_along, order) tuples
    
    Returns:
        List of link IDs that are next in sequence
    """
    next_link_ids = []
    
    # Find the next link(s) - could be multiple if there are gaps
    # For now, return the immediate next link
    if current_order + 1 < len(ordered_links):
        next_link, _, _ = ordered_links[current_order + 1]
        next_link_ids.append(next_link['LinkID'])
    
    return next_link_ids


def process_route(df, service_no, direction, all_links, buffer_meters):
    """
    Process a single route to find and order links.
    
    Args:
        df: DataFrame with geometry data
        service_no: Service number
        direction: Direction (1 or 2)
        all_links: List of all link dictionaries
        buffer_meters: Buffer distance in meters
    
    Returns:
        Dictionary with route data and ordered links
    """
    print(f"\nProcessing Bus {service_no} - Direction {direction}...")
    
    # Get route LineString
    route_linestring = get_route_linestring(df, service_no, direction)
    if route_linestring is None:
        print(f"  No geometry found for this route")
        return None
    
    print(f"  Route LineString created with {len(route_linestring.coords)} points")
    
    # Find links in buffer
    print(f"  Finding links within {buffer_meters}m buffer...")
    matching_links = find_links_in_buffer(route_linestring, all_links, buffer_meters)
    print(f"  Found {len(matching_links)} links in buffer")
    
    if not matching_links:
        print(f"  No links found for this route")
        return None
    
    # Order links along route
    print(f"  Ordering links along route...")
    ordered_links = order_links_along_route(matching_links, route_linestring)
    print(f"  Ordered {len(ordered_links)} links")
    
    # Build output structure
    route_data = {
        'ServiceNo': int(service_no),
        'Direction': int(direction),
        'buffer_meters': buffer_meters,
        'ordered_links': [],
        'link_index': {}
    }
    
    # Process each ordered link
    for link, distance_along, order in ordered_links:
        # Find connectivity
        inbound_link_ids = find_inbound_links(link, matching_links, buffer_meters)
        outbound_link_ids = find_outbound_links(link, matching_links, buffer_meters)
        next_link_ids = find_next_links(order, ordered_links)
        
        # Create link entry with all original fields plus connectivity
        link_entry = link.copy()
        link_entry['order'] = order
        link_entry['distance_along_route'] = float(distance_along)
        link_entry['inbound_link_ids'] = inbound_link_ids
        link_entry['outbound_link_ids'] = outbound_link_ids
        link_entry['next_link_ids'] = next_link_ids
        
        route_data['ordered_links'].append(link_entry)
        route_data['link_index'][link['LinkID']] = link_entry
    
    print(f"  Processed {len(route_data['ordered_links'])} links with connectivity")
    
    return route_data


def find_current_link(lat, lon, ordered_links):
    """
    Find the closest link to a given position.
    
    Args:
        lat: Latitude
        lon: Longitude
        ordered_links: List of link dictionaries with order and connectivity
    
    Returns:
        Link dictionary or None if not found
    """
    min_distance = float('inf')
    closest_link = None
    
    point = Point(lon, lat)  # Shapely uses (lon, lat)
    
    for link in ordered_links:
        try:
            link_line = create_link_linestring(link)
            if link_line is None:
                continue
            
            # Calculate distance from point to link
            distance = point.distance(link_line)
            
            if distance < min_distance:
                min_distance = distance
                closest_link = link
        except Exception:
            continue
    
    return closest_link


def get_link_connectivity(link_id, route_data):
    """
    Get inbound/outbound/next links for a given link ID.
    
    Args:
        link_id: Link ID string
        route_data: Route data dictionary
    
    Returns:
        Dictionary with inbound_link_ids, outbound_link_ids, next_link_ids
    """
    if link_id not in route_data['link_index']:
        return None
    
    link_entry = route_data['link_index'][link_id]
    
    return {
        'inbound_link_ids': link_entry.get('inbound_link_ids', []),
        'outbound_link_ids': link_entry.get('outbound_link_ids', []),
        'next_link_ids': link_entry.get('next_link_ids', [])
    }


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Find and order links along bus routes using geometry-based buffering'
    )
    parser.add_argument(
        '--source',
        choices=['onemap', 'osrm', 'auto'],
        default='auto',
        help='Source of geometry data: onemap, osrm, or auto (default: auto)'
    )
    parser.add_argument(
        '--csv',
        type=str,
        default=None,
        help='Custom path to geometry CSV file (overrides --source)'
    )
    parser.add_argument(
        '--buffer',
        type=float,
        default=BUFFER_METERS,
        help=f'Buffer distance in meters (default: {BUFFER_METERS})'
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
            return
    
    # Check if CSV file exists
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return
    
    # Load geometry data
    print(f"Loading geometry data from {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} route segments")
    
    # Load links
    if not os.path.exists(LINKS_JSON_PATH):
        print(f"Error: Links JSON file not found at {LINKS_JSON_PATH}")
        return
    
    print(f"Loading links from {LINKS_JSON_PATH}...")
    with open(LINKS_JSON_PATH, 'r') as f:
        all_links = json.load(f)
    print(f"Loaded {len(all_links)} links")
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Group by ServiceNo and Direction
    grouped = df.groupby(['ServiceNo', 'Direction'])
    
    # Process each route
    for (service_no, direction), _ in grouped:
        route_data = process_route(df, service_no, direction, all_links, args.buffer)
        
        if route_data is None:
            continue
        
        # Save to JSON file
        output_file = os.path.join(
            OUTPUT_DIR,
            f"links_by_geometry_{service_no}_{direction}.json"
        )
        
        with open(output_file, 'w') as f:
            json.dump(route_data, f, indent=2)
        
        print(f"  Saved to {output_file}")
        print(f"  Total links: {len(route_data['ordered_links'])}")
    
    print("\nDone!")


if __name__ == "__main__":
    main()
