"""
Service for fetching and processing bus routes.
"""
import requests
import pandas as pd
import time
import json
from typing import Dict, Any, Optional, List
from shapely.geometry import LineString, Point
from shapely.ops import transform
import pyproj

from backend.config import (
    DATAMALL_BUS_ROUTES, DATAMALL_BUS_STOPS, LTA_DATAMALL_KEY,
    LINKS_JSON_PATH, ROUTE_BUFFER_METERS, DATAMALL_PAGE_SIZE,
    SINGAPORE_UTM, WGS84
)
from backend.cache import route_cache


# Load links once at module level
_all_links: Optional[List[Dict[str, Any]]] = None
_link_position_index: Optional[Dict[str, int]] = None


def load_links() -> List[Dict[str, Any]]:
    """Load all links from links.json."""
    global _all_links
    if _all_links is None:
        if not LINKS_JSON_PATH.exists():
            raise FileNotFoundError(f"Links file not found at {LINKS_JSON_PATH}")
        with open(LINKS_JSON_PATH, 'r') as f:
            _all_links = json.load(f)
        if not _all_links:
            raise ValueError(f"Links file is empty at {LINKS_JSON_PATH}")
    return _all_links


def get_link_position_index() -> Dict[str, int]:
    """
    Get index mapping LinkID to position in the links list.
    Position is 0-indexed (e.g., first link is position 0).
    """
    global _link_position_index, _all_links
    if _link_position_index is None:
        # Ensure links are loaded
        if _all_links is None:
            load_links()
        
        # Create position index: LinkID -> position
        _link_position_index = {}
        for position, link in enumerate(_all_links):
            link_id = str(link.get('LinkID', ''))
            if link_id:
                _link_position_index[link_id] = position
    
    return _link_position_index


def fetch_all_paginated(url: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Fetch all data from a paginated LTA DataMall API endpoint.
    
    Args:
        url: API endpoint URL
        headers: Request headers with authentication
    
    Returns:
        List of all records
    """
    results = []
    skip = 0
    
    while True:
        req_url = f"{url}?$skip={skip}"
        
        try:
            response = requests.get(req_url, headers=headers)
            if response.status_code != 200:
                break
            
            data = response.json()
            values = data.get('value', [])
            
            if not values:
                break
            
            results.extend(values)
            skip += DATAMALL_PAGE_SIZE
            
            # Respect API rate limits
            time.sleep(0.1)
            
        except Exception as e:
            print(f"Error fetching data: {e}")
            break
    
    return results


def create_link_linestring(link: Dict[str, Any]) -> Optional[LineString]:
    """Create a Shapely LineString from a link dictionary."""
    try:
        start_lat = float(link['StartLat'])
        start_lon = float(link['StartLon'])
        end_lat = float(link['EndLat'])
        end_lon = float(link['EndLon'])
        return LineString([(start_lon, start_lat), (end_lon, end_lat)])
    except (ValueError, KeyError):
        return None


def find_links_in_buffer(route_linestring: LineString, all_links: List[Dict[str, Any]], 
                         buffer_meters: float) -> List[Dict[str, Any]]:
    """Find links that fall within a buffer range of the route."""
    if route_linestring is None or route_linestring.is_empty:
        return []
    
    transformer_to_utm = pyproj.Transformer.from_crs(WGS84, SINGAPORE_UTM, always_xy=True)
    transformer_to_wgs84 = pyproj.Transformer.from_crs(SINGAPORE_UTM, WGS84, always_xy=True)
    
    route_utm = transform(transformer_to_utm.transform, route_linestring)
    buffered_route_utm = route_utm.buffer(buffer_meters)
    buffered_route = transform(transformer_to_wgs84.transform, buffered_route_utm)
    
    matching_links = []
    for link in all_links:
        link_line = create_link_linestring(link)
        if link_line is None:
            continue
        if link_line.intersects(buffered_route):
            matching_links.append(link)
    
    return matching_links


def order_links_along_route(links: List[Dict[str, Any]], 
                            route_linestring: LineString) -> List[tuple]:
    """Order links by their position along the route."""
    if route_linestring is None or route_linestring.is_empty:
        return []
    
    link_positions = []
    for link in links:
        link_line = create_link_linestring(link)
        if link_line is None:
            continue
        
        midpoint = link_line.interpolate(0.5, normalized=True)
        closest_point = route_linestring.interpolate(
            route_linestring.project(midpoint)
        )
        distance_along = route_linestring.project(closest_point)
        link_positions.append((link, distance_along))
    
    link_positions.sort(key=lambda x: x[1])
    
    ordered_links = []
    for order, (link, distance_along) in enumerate(link_positions):
        ordered_links.append((link, distance_along, order))
    
    return ordered_links


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points in meters."""
    import math
    R = 6371000
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def points_match(lat1: float, lon1: float, lat2: float, lon2: float, 
                buffer_meters: float) -> bool:
    """Check if two points are within the buffer distance."""
    distance = haversine_distance(lat1, lon1, lat2, lon2)
    return distance <= buffer_meters


def find_inbound_links(current_link: Dict[str, Any], all_links: List[Dict[str, Any]], 
                      buffer_meters: float) -> List[str]:
    """Find links whose END point is within buffer of current link's START point."""
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
            if points_match(current_start_lat, current_start_lon, 
                          link_end_lat, link_end_lon, buffer_meters):
                inbound_link_ids.append(link['LinkID'])
        except (ValueError, KeyError):
            continue
    
    return inbound_link_ids


def find_outbound_links(current_link: Dict[str, Any], all_links: List[Dict[str, Any]], 
                       buffer_meters: float) -> List[str]:
    """Find links whose START point is within buffer of current link's END point."""
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
            if points_match(current_end_lat, current_end_lon,
                          link_start_lat, link_start_lon, buffer_meters):
                outbound_link_ids.append(link['LinkID'])
        except (ValueError, KeyError):
            continue
    
    return outbound_link_ids


def find_next_links(current_order: int, ordered_links: List[tuple]) -> List[str]:
    """Find the next link(s) in the ordered sequence."""
    next_link_ids = []
    if current_order + 1 < len(ordered_links):
        next_link, _, _ = ordered_links[current_order + 1]
        next_link_ids.append(next_link['LinkID'])
    return next_link_ids


def get_route_linestring_from_stops(df: pd.DataFrame, service_no: str, 
                                    direction: int) -> Optional[LineString]:
    """Create a LineString from bus stop coordinates."""
    route_df = df[(df['ServiceNo'] == service_no) & (df['Direction'] == direction)]
    
    if route_df.empty:
        return None
    
    sorted_df = route_df.sort_values('StopSequence')
    
    coords = []
    for _, row in sorted_df.iterrows():
        if pd.notna(row.get('Latitude')) and pd.notna(row.get('Longitude')):
            lat = float(row['Latitude'])
            lon = float(row['Longitude'])
            coords.append((lon, lat))  # Shapely uses (lon, lat)
    
    if len(coords) < 2:
        return None
    
    return LineString(coords)


def process_route(service_no: str, direction: int, 
                  all_links: List[Dict[str, Any]], buffer_meters: float) -> Optional[Dict[str, Any]]:
    """Process a route to find and order links."""
    # Fetch bus routes and stops
    headers = {
        'AccountKey': LTA_DATAMALL_KEY,
        'accept': 'application/json'
    }
    
    print(f"Fetching bus routes for service {service_no} direction {direction}...")
    routes_data = fetch_all_paginated(DATAMALL_BUS_ROUTES, headers)
    if not routes_data:
        return None
    
    print(f"Fetching bus stops...")
    stops_data = fetch_all_paginated(DATAMALL_BUS_STOPS, headers)
    if not stops_data:
        return None
    
    # Convert to DataFrames
    df_routes = pd.DataFrame(routes_data)
    df_stops = pd.DataFrame(stops_data)
    
    # Filter routes for this service and direction
    df_target_routes = df_routes[
        (df_routes['ServiceNo'] == service_no) & 
        (df_routes['Direction'] == direction)
    ].copy()
    
    if df_target_routes.empty:
        return None
    
    # Merge with bus stops
    df_merged = pd.merge(
        df_target_routes,
        df_stops[['BusStopCode', 'Latitude', 'Longitude', 'Description', 'RoadName']],
        on='BusStopCode',
        how='left'
    )
    
    df_merged = df_merged.sort_values(by=['ServiceNo', 'Direction', 'StopSequence'])
    
    # Create route LineString
    route_linestring = get_route_linestring_from_stops(df_merged, service_no, direction)
    if route_linestring is None:
        return None
    
    # Find links in buffer
    matching_links = find_links_in_buffer(route_linestring, all_links, buffer_meters)
    if not matching_links:
        return None
    
    # Order links along route
    ordered_links = order_links_along_route(matching_links, route_linestring)
    
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
        inbound_link_ids = find_inbound_links(link, matching_links, buffer_meters)
        outbound_link_ids = find_outbound_links(link, matching_links, buffer_meters)
        next_link_ids = find_next_links(order, ordered_links)
        
        link_entry = link.copy()
        link_entry['order'] = order
        link_entry['distance_along_route'] = float(distance_along)
        link_entry['inbound_link_ids'] = inbound_link_ids
        link_entry['outbound_link_ids'] = outbound_link_ids
        link_entry['next_link_ids'] = next_link_ids
        
        route_data['ordered_links'].append(link_entry)
        route_data['link_index'][link['LinkID']] = link_entry
    
    return route_data


def get_route_links(service_no: int, direction: int) -> Optional[Dict[str, Any]]:
    """
    Get route links for a bus service and direction.
    Returns cached data if available, otherwise fetches and processes.
    """
    # Check cache first
    if route_cache.has(service_no, direction):
        return route_cache.get(service_no, direction)
    
    # Load links
    all_links = load_links()
    print(f"Loaded {len(all_links)} links")
    

    # Process route
    route_data = process_route(str(service_no), direction, all_links, ROUTE_BUFFER_METERS)
    print(f"Processed route data for service {service_no} direction {direction}")
    
    if route_data:
        # Cache the result
        route_cache.set(service_no, direction, route_data)
        print(f"Cached route data for service {service_no} direction {direction}")
    
    return route_data
