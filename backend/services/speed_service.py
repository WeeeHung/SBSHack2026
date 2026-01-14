"""
Service for fetching speed band data.
"""
import requests
import time
from typing import Dict, Any, List, Set
from dotenv import load_dotenv

from backend.config import (
    DATAMALL_TRAFFIC_SPEED_BANDS, LTA_DATAMALL_KEY, DATAMALL_PAGE_SIZE
)
from backend.services.route_service import get_link_position_index

# Load environment variables
load_dotenv()


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
            print(f"Error fetching speed band data: {e}")
            break
    
    return results


def fetch_speed_bands() -> Dict[str, Any]:
    """
    Fetch speed band data from LTA DataMall API.
    Always fetches fresh data (no caching - data updates every 5 minutes).
    
    Returns:
        Dictionary mapping LinkID to speed band data
    """
    # Fetch from API (always fresh, no cache)
    headers = {
        "AccountKey": LTA_DATAMALL_KEY,
        "accept": "application/json"
    }
    
    speed_bands_list = fetch_all_paginated(DATAMALL_TRAFFIC_SPEED_BANDS, headers)
    
    # Convert to dictionary: {LinkID: {speedband, minspeed, maxspeed, ...}}
    speed_bands_dict = {}
    for band in speed_bands_list:
        link_id = str(band.get('LinkID', ''))
        if link_id:
            speed_bands_dict[link_id] = {
                'speedband': band.get('SpeedBand'),
                'minspeed': band.get('MinimumSpeed'),
                'maxspeed': band.get('MaximumSpeed'),
                'start_coord': [band.get('StartLat'), band.get('StartLon')],
                'end_coord': [band.get('EndLat'), band.get('EndLon')],
                'road_name': band.get('RoadName'),
                'road_category': band.get('RoadCategory')
            }
    
    return speed_bands_dict


def fetch_speed_bands_for_links(link_ids: List[str]) -> Dict[str, Any]:
    """
    Fetch speed band data only for specific link IDs.
    Optimized to fetch only the pages containing the needed link IDs using position index.
    
    Args:
        link_ids: List of LinkID strings to fetch
    
    Returns:
        Dictionary mapping LinkID to speed band data (only for requested links)
    """
    if not link_ids:
        return {}
    
    # Get link position index
    link_position_index = get_link_position_index()
    
    # Convert to set for faster lookup
    needed_link_ids = set(str(link_id) for link_id in link_ids)
    speed_bands_dict = {}
    
    # Calculate which pages we need to fetch based on link positions
    pages_to_fetch = set()
    link_positions = {}
    
    for link_id in needed_link_ids:
        position = link_position_index.get(link_id)
        if position is not None:
            # Calculate which page this link is on (0-indexed page number)
            page = position // DATAMALL_PAGE_SIZE
            pages_to_fetch.add(page)
            link_positions[link_id] = position
        else:
            # Link not found in index, we'll need to search all pages
            print(f"Warning: LinkID {link_id} not found in position index, will need full search")
            pages_to_fetch = None  # Signal to do full search
            break
    
    headers = {
        "AccountKey": LTA_DATAMALL_KEY,
        "accept": "application/json"
    }
    
    if pages_to_fetch is not None:
        # Optimized: fetch only the specific pages we need
        print(f"[Speed Service] Fetching {len(pages_to_fetch)} page(s) for {len(needed_link_ids)} link IDs")
        for page in sorted(pages_to_fetch):
            skip = page * DATAMALL_PAGE_SIZE
            req_url = f"{DATAMALL_TRAFFIC_SPEED_BANDS}?$skip={skip}"
            
            try:
                print(f"[Speed Service] Making API call: page {page} (skip={skip})")
                response = requests.get(req_url, headers=headers)
                if response.status_code != 200:
                    continue
                
                data = response.json()
                values = data.get('value', [])
                
                if not values:
                    continue
                
                # Process this page and collect only the bands we need
                for band in values:
                    link_id = str(band.get('LinkID', ''))
                    if link_id in needed_link_ids and link_id not in speed_bands_dict:
                        speed_bands_dict[link_id] = {
                            'speedband': band.get('SpeedBand'),
                            'minspeed': band.get('MinimumSpeed'),
                            'maxspeed': band.get('MaximumSpeed'),
                            'start_coord': [band.get('StartLat'), band.get('StartLon')],
                            'end_coord': [band.get('EndLat'), band.get('EndLon')],
                            'road_name': band.get('RoadName'),
                            'road_category': band.get('RoadCategory')
                        }
                
                # Respect API rate limits
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error fetching speed band data for page {page}: {e}")
                continue
    else:
        # Fallback: do full pagination if some links not found in index
        found_link_ids = set()
        skip = 0
        
        while len(found_link_ids) < len(needed_link_ids):
            req_url = f"{DATAMALL_TRAFFIC_SPEED_BANDS}?$skip={skip}"
            
            try:
                response = requests.get(req_url, headers=headers)
                if response.status_code != 200:
                    break
                
                data = response.json()
                values = data.get('value', [])
                
                if not values:
                    break
                
                # Process this page and collect only the bands we need
                for band in values:
                    link_id = str(band.get('LinkID', ''))
                    if link_id in needed_link_ids and link_id not in found_link_ids:
                        speed_bands_dict[link_id] = {
                            'speedband': band.get('SpeedBand'),
                            'minspeed': band.get('MinimumSpeed'),
                            'maxspeed': band.get('MaximumSpeed'),
                            'start_coord': [band.get('StartLat'), band.get('StartLon')],
                            'end_coord': [band.get('EndLat'), band.get('EndLon')],
                            'road_name': band.get('RoadName'),
                            'road_category': band.get('RoadCategory')
                        }
                        found_link_ids.add(link_id)
                
                # If we found all the links we need, stop fetching
                if len(found_link_ids) >= len(needed_link_ids):
                    break
                
                skip += DATAMALL_PAGE_SIZE
                
                # Respect API rate limits
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error fetching speed band data: {e}")
                break
    
    return speed_bands_dict


def get_speed_bands_for_links(link_ids: List[str], 
                              speed_bands_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter speed band data for specific link IDs.
    (Legacy function - use fetch_speed_bands_for_links for optimized fetching)
    
    Args:
        link_ids: List of LinkID strings
        speed_bands_data: Full speed bands dictionary
    
    Returns:
        Dictionary with speed band data for requested links
    """
    result = {}
    link_ids_set = set(link_ids)
    
    for link_id in link_ids_set:
        if link_id in speed_bands_data:
            result[link_id] = speed_bands_data[link_id]
    
    return result
