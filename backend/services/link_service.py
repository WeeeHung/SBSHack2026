"""
Service for finding current link and associated links.
"""
from typing import Dict, Any, Optional, List
from shapely.geometry import Point, LineString

from backend.config import NUM_FUTURE_LINKS


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


def get_current_link(lat: float, lon: float, 
                    ordered_links: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Find the closest link to GPS coordinates.
    
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
    
    distances = []
    
    for link in ordered_links:
        try:
            link_line = create_link_linestring(link)
            if link_line is None:
                continue
            
            # Calculate distance in degrees (Shapely distance returns degrees)
            distance = point.distance(link_line)
            link_order = link.get('order', -1)
            link_id = link.get('LinkID', 'unknown')
            
            distances.append({
                'order': link_order,
                'link_id': link_id,
                'distance': distance
            })
            
            if distance < min_distance:
                min_distance = distance
                closest_link = link
        except Exception as e:
            print(f"[get_current_link] Error processing link: {e}")
            continue
    
    # Print top 5 closest links for debugging
    distances.sort(key=lambda x: x['distance'])
    print(f"[get_current_link] GPS point: ({lat}, {lon})")
    print(f"[get_current_link] Top 5 closest links:")
    for i, dist_info in enumerate(distances[:5]):
        print(f"  {i+1}. Order {dist_info['order']}, LinkID {dist_info['link_id']}, Distance: {dist_info['distance']:.6f} degrees")
    
    if closest_link:
        print(f"[get_current_link] Selected: Order {closest_link.get('order')}, LinkID {closest_link.get('LinkID')}, Distance: {min_distance:.6f} degrees")
    
    return closest_link


def get_links_for_analysis(current_link: Dict[str, Any], route_data: Dict[str, Any],
                           num_future_links: int = NUM_FUTURE_LINKS) -> List[Dict[str, Any]]:
    """
    Get all links needed for analysis: current + next few + their inbounds/outbounds.
    
    Args:
        current_link: Current link dictionary
        route_data: Route data with link_index
        num_future_links: Number of future links to include
    
    Returns:
        List of all relevant links for speed band/incident/rainfall checking
    """
    link_index = route_data.get('link_index', {})
    links_for_analysis = []
    link_ids_seen = set()
    
    # Add current link
    current_link_id = current_link.get('LinkID')
    if current_link_id and current_link_id in link_index:
        links_for_analysis.append(link_index[current_link_id])
        link_ids_seen.add(current_link_id)
    
    # Add next few links
    current_order = current_link.get('order', -1)
    ordered_links = route_data.get('ordered_links', [])
    
    for i in range(1, num_future_links + 1):
        next_order = current_order + i
        if next_order < len(ordered_links):
            next_link = ordered_links[next_order]
            next_link_id = next_link.get('LinkID')
            if next_link_id and next_link_id not in link_ids_seen:
                links_for_analysis.append(next_link)
                link_ids_seen.add(next_link_id)
    
    # Add inbounds and outbounds of current + next links
    for link in links_for_analysis[:]:  # Use slice to avoid modifying while iterating
        link_id = link.get('LinkID')
        
        # Add inbound links
        for inbound_id in link.get('inbound_link_ids', []):
            if inbound_id not in link_ids_seen and inbound_id in link_index:
                links_for_analysis.append(link_index[inbound_id])
                link_ids_seen.add(inbound_id)
        
        # Add outbound links
        for outbound_id in link.get('outbound_link_ids', []):
            if outbound_id not in link_ids_seen and outbound_id in link_index:
                links_for_analysis.append(link_index[outbound_id])
                link_ids_seen.add(outbound_id)
    
    return links_for_analysis
