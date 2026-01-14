"""
Continuous correlation of traffic speed bands, rainfall, and traffic incidents.
Fetches data from APIs every 5 minutes and appends to Parquet file.
"""
import json
import math
import os
import time
import requests
import pandas as pd
from datetime import datetime
from typing import Any, Dict, List, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

ROOT_DIR = os.path.dirname(os.path.abspath(os.path.join(__file__, os.pardir)))

# API endpoints
LTA_BASE_URL = "https://datamall2.mytransport.sg/ltaodataservice/v4"
RAINFALL_API_URL = "https://api.data.gov.sg/v1/environment/rainfall"
INCIDENTS_API_URL = "https://datamall2.mytransport.sg/ltaodataservice/TrafficIncidents"

# Static data files (loaded once)
LINKS_FILE = os.path.join(ROOT_DIR, "speed_bands", "data", "links.json")
OUT_DIR = os.path.dirname(__file__)
LINK_GEOMETRY_OUT = os.path.join(OUT_DIR, "link_geometry.json")
RAINFALL_STATIONS_OUT = os.path.join(OUT_DIR, "rainfall_stations.json")
CORRELATED_OUT = os.path.join(OUT_DIR, "correlated_traffic_data.parquet")

# Collection interval (seconds)
COLLECTION_INTERVAL = 300  # 5 minutes

# API request timeout (seconds)
REQUEST_TIMEOUT = 30  # 30 seconds timeout for API requests


def truncate_ts(ts: str) -> str:
    """
    Truncate ISO timestamp to seconds precision (drop microseconds / timezone offset).
    Examples:
      2026-01-13T15:00:52.462434 -> 2026-01-13T15:00:52
      2026-01-14T18:30:00+08:00 -> 2026-01-14T18:30:00
    """
    if "T" not in ts:
        return ts
    date_part, time_part = ts.split("T", 1)
    # Strip timezone
    for sep in ["+", "-"]:
        if sep in time_part:
            time_part = time_part.split(sep, 1)[0]
            break
    # Strip microseconds
    if "." in time_part:
        time_part = time_part.split(".", 1)[0]
    return f"{date_part}T{time_part}"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in km between two lat/lon points."""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def point_to_segment_distance_km(
    lat: float,
    lon: float,
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Approximate distance in km from point (lat, lon) to line segment (lat1, lon1)-(lat2, lon2).
    Uses simple equirectangular projection which is fine at Singapore scale.
    """
    phi = math.radians(lat)
    x = math.radians(lon)
    x1 = math.radians(lon1)
    x2 = math.radians(lon2)
    y = math.radians(lat)
    y1 = math.radians(lat1)
    y2 = math.radians(lat2)

    def proj(xx: float, yy: float) -> Tuple[float, float]:
        return (xx * math.cos(phi), yy)

    px, py = proj(x, y)
    p1x, p1y = proj(x1, y1)
    p2x, p2y = proj(x2, y2)

    dx = p2x - p1x
    dy = p2y - p1y
    if dx == 0 and dy == 0:
        return haversine_km(lat, lon, lat1, lon1)

    t = ((px - p1x) * dx + (py - p1y) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x = p1x + t * dx
    proj_y = p1y + t * dy

    proj_lon = math.degrees(proj_x / math.cos(phi))
    proj_lat = math.degrees(proj_y)
    return haversine_km(lat, lon, proj_lat, proj_lon)


def get_lta_headers() -> Dict[str, str]:
    """Get LTA DataMall API headers."""
    account_key = os.getenv("LTA_DATAMALL")
    if not account_key:
        raise ValueError(
            "LTA_DATAMALL not found in environment variables. "
            "Please set it in your .env file or environment."
        )
    return {
        "AccountKey": account_key,
        "accept": "application/json"
    }


def fetch_all_speed_bands() -> Dict[str, Any]:
    """Fetch all speed band data from API (handles pagination)."""
    start_time = time.time()
    headers = get_lta_headers()
    endpoint = f"{LTA_BASE_URL}/TrafficSpeedBands"
    all_bands = []
    skip = 0
    max_records_per_page = 500
    page = 1

    while True:
        page_start = time.time()
        params = {"$skip": skip} if skip > 0 else {}
        try:
            # Log request start for pages that might take longer
            if page % 50 == 0 or page > 100:
                print(f"    Requesting page {page} (skip={skip})...")
            
            # Add timeout and retry logic
            response = requests.get(endpoint, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            
            if "value" not in data:
                print(f"    Page {page}: No 'value' key in response, stopping")
                break
            
            bands = data["value"]
            if not bands:
                print(f"    Page {page}: Empty bands array, stopping")
                break
            
            all_bands.extend(bands)
            page_time = time.time() - page_start
            print(f"    Page {page}: Fetched {len(bands)} records (total: {len(all_bands)}) in {page_time:.2f}s")
            
            if len(bands) < max_records_per_page:
                print(f"    Page {page}: Got {len(bands)} < {max_records_per_page} records, reached end")
                break
            
            # Sleep 0.1s between API calls to avoid rate limiting
            time.sleep(0.1)
            
            skip += max_records_per_page
            page += 1
            
            # Safety check: if we've fetched more than expected, log a warning
            if page > 500:  # Safety limit
                print(f"    WARNING: Reached page {page}, stopping to prevent infinite loop")
                break
                
        except requests.exceptions.Timeout as e:
            print(f"    ERROR: Timeout on page {page} after {REQUEST_TIMEOUT}s: {e}")
            raise
        except requests.exceptions.RequestException as e:
            print(f"    ERROR: Request failed on page {page}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"    Response status: {e.response.status_code}")
                print(f"    Response text: {e.response.text[:200]}")
            raise
        except Exception as e:
            print(f"    ERROR: Unexpected error on page {page}: {e}")
            raise

    total_time = time.time() - start_time
    print(f"    Total: {len(all_bands)} speed bands fetched in {total_time:.2f}s")
    return {"value": all_bands}


def fetch_rainfall() -> Dict[str, Any]:
    """Fetch rainfall data from data.gov.sg API."""
    start_time = time.time()
    try:
        response = requests.get(RAINFALL_API_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        elapsed = time.time() - start_time
        print(f"    Fetched rainfall data in {elapsed:.2f}s")
        return data
    except requests.exceptions.Timeout as e:
        print(f"    ERROR: Timeout fetching rainfall after {REQUEST_TIMEOUT}s: {e}")
        raise
    except requests.exceptions.RequestException as e:
        print(f"    ERROR: Request failed fetching rainfall: {e}")
        raise


def fetch_incidents() -> Dict[str, Any]:
    """Fetch traffic incidents from LTA DataMall API."""
    start_time = time.time()
    headers = get_lta_headers()
    try:
        response = requests.get(INCIDENTS_API_URL, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        elapsed = time.time() - start_time
        print(f"    Fetched {len(data.get('value', []))} incidents in {elapsed:.2f}s")
        return data
    except requests.exceptions.Timeout as e:
        print(f"    ERROR: Timeout fetching incidents after {REQUEST_TIMEOUT}s: {e}")
        raise
    except requests.exceptions.RequestException as e:
        print(f"    ERROR: Request failed fetching incidents: {e}")
        raise


def build_link_geometry(links: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Extract static geometry + basic metadata for each LinkID."""
    geom: Dict[str, Dict[str, Any]] = {}
    for link in links:
        link_id = str(link.get("LinkID"))
        if not link_id:
            continue
        try:
            start_lat = float(link.get("StartLat"))
            start_lon = float(link.get("StartLon"))
            end_lat = float(link.get("EndLat"))
            end_lon = float(link.get("EndLon"))
        except (TypeError, ValueError):
            continue
        geom[link_id] = {
            "StartLat": start_lat,
            "StartLon": start_lon,
            "EndLat": end_lat,
            "EndLon": end_lon,
            "RoadName": link.get("RoadName"),
            "RoadCategory": link.get("RoadCategory"),
        }
    return geom


def build_rainfall_stations(rain_obj: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, float]]:
    """
    Return:
      stations: {station_id: {latitude, longitude, name}}
      readings: {station_id: rainfall_mm}
    """
    items = rain_obj.get("items", [])
    meta = rain_obj.get("metadata", {})

    stations: Dict[str, Dict[str, Any]] = {}
    for s in meta.get("stations", []):
        sid = s.get("id")
        if not sid:
            continue
        loc = s.get("location", {})
        try:
            stations[sid] = {
                "latitude": float(loc.get("latitude")),
                "longitude": float(loc.get("longitude")),
                "name": s.get("name"),
            }
        except (TypeError, ValueError):
            continue

    readings: Dict[str, float] = {}
    if items:
        item0 = items[0]
        for r in item0.get("readings", []):
            sid = r.get("station_id")
            val = r.get("value")
            if sid is None or val is None:
                continue
            try:
                readings[sid] = float(val)
            except (TypeError, ValueError):
                continue

    return stations, readings


def find_nearest_station_rainfall(
    link_geom: Dict[str, Any],
    stations: Dict[str, Dict[str, Any]],
    readings: Dict[str, float],
) -> float:
    """Return rainfall_mm from nearest station (0.0 if nothing found)."""
    if not stations or not readings:
        return 0.0

    start_lat = link_geom["StartLat"]
    start_lon = link_geom["StartLon"]
    end_lat = link_geom["EndLat"]
    end_lon = link_geom["EndLon"]
    mid_lat = (start_lat + end_lat) / 2.0
    mid_lon = (start_lon + end_lon) / 2.0

    best_sid = None
    best_dist = float("inf")
    for sid, s in stations.items():
        if sid not in readings:
            continue
        d = haversine_km(mid_lat, mid_lon, s["latitude"], s["longitude"])
        if d < best_dist:
            best_dist = d
            best_sid = sid

    if best_sid is None:
        return 0.0
    return readings.get(best_sid, 0.0)


def build_speed_snapshot(speed_data: Dict[str, Any]) -> Dict[str, int]:
    """
    Build snapshot of latest speed band for each link.
    Returns: {LinkID: speedband}
    """
    start_time = time.time()
    snapshot: Dict[str, int] = {}
    bands = speed_data.get("value", [])
    
    for band in bands:
        link_id = str(band.get("LinkID"))
        speedband = band.get("SpeedBand")
        if link_id and speedband is not None:
            snapshot[link_id] = speedband
    
    elapsed = time.time() - start_time
    print(f"    Built speed snapshot: {len(snapshot)} links in {elapsed:.2f}s")
    return snapshot


def build_incident_index(inc_obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return list of incidents with lat/lon/message."""
    incidents = inc_obj.get("value", [])
    cleaned: List[Dict[str, Any]] = []
    for inc in incidents:
        try:
            lat = float(inc.get("Latitude"))
            lon = float(inc.get("Longitude"))
        except (TypeError, ValueError):
            continue
        cleaned.append(
            {
                "Type": inc.get("Type"),
                "Latitude": lat,
                "Longitude": lon,
                "Message": inc.get("Message", "") or "",
            }
        )
    return cleaned


def link_has_incident(
    link_geom: Dict[str, Any],
    road_name: str,
    incidents: List[Dict[str, Any]],
    distance_threshold_km: float = 0.1,
) -> bool:
    """Match by road name first, then by distance if no name match."""
    rn = (road_name or "").lower()
    if rn:
        for inc in incidents:
            msg = inc.get("Message", "").lower()
            if rn in msg:
                return True

    if not incidents:
        return False

    start_lat = link_geom["StartLat"]
    start_lon = link_geom["StartLon"]
    end_lat = link_geom["EndLat"]
    end_lon = link_geom["EndLon"]

    for inc in incidents:
        lat = inc["Latitude"]
        lon = inc["Longitude"]
        d = point_to_segment_distance_km(lat, lon, start_lat, start_lon, end_lat, end_lon)
        if d <= distance_threshold_km:
            return True

    return False


def save_geometry_files(links: List[Dict[str, Any]], rain_obj: Dict[str, Any]) -> None:
    """Save static geometry files (only need to do this once)."""
    if not os.path.exists(LINK_GEOMETRY_OUT):
        print("Creating link geometry file...")
        link_geom = build_link_geometry(links)
        with open(LINK_GEOMETRY_OUT, "w", encoding="utf-8") as f:
            json.dump(link_geom, f, indent=2)
        print(f"Saved link geometry for {len(link_geom)} links")

    if not os.path.exists(RAINFALL_STATIONS_OUT):
        print("Creating rainfall stations file...")
        stations, _ = build_rainfall_stations(rain_obj)
        with open(RAINFALL_STATIONS_OUT, "w", encoding="utf-8") as f:
            json.dump(stations, f, indent=2)
        print(f"Saved {len(stations)} rainfall stations")


def collect_and_append(links: List[Dict[str, Any]], link_geom: Dict[str, Dict[str, Any]]) -> None:
    """Collect data from APIs, correlate, and append to Parquet file."""
    cycle_start = time.time()
    generated_at = truncate_ts(datetime.now().isoformat())
    print(f"\n[{generated_at}] Starting collection cycle...")

    # Fetch data from APIs
    print("  Fetching speed bands from API...")
    speed_data = fetch_all_speed_bands()
    speed_snapshot = build_speed_snapshot(speed_data)
    print(f"  [OK] Got {len(speed_snapshot)} links with speed data")

    print("  Fetching rainfall from API...")
    rain_obj = fetch_rainfall()
    stations, readings = build_rainfall_stations(rain_obj)
    print(f"  [OK] Got {len(readings)} station readings")

    print("  Fetching traffic incidents from API...")
    inc_obj = fetch_incidents()
    incidents = build_incident_index(inc_obj)
    print(f"  [OK] Got {len(incidents)} incidents")
    
    api_time = time.time() - cycle_start
    print(f"  API fetching completed in {api_time:.2f}s")

    # Correlate data
    print("  Correlating data per link...")
    correlate_start = time.time()
    rows = []
    total_links = len(links)
    processed = 0
    last_log_time = time.time()
    
    for i, link in enumerate(links):
        link_id = str(link.get("LinkID"))
        if link_id not in link_geom:
            continue

        geom = link_geom[link_id]
        road_name = geom.get("RoadName") or link.get("RoadName") or ""

        # Speed band (may be missing)
        speedband = speed_snapshot.get(link_id)

        # Rainfall from nearest station
        rainfall_mm = find_nearest_station_rainfall(geom, stations, readings)

        # Incident flag
        has_inc = link_has_incident(geom, road_name, incidents)

        rows.append({
            "LinkID": link_id,
            "generated_at": generated_at,
            "speedband": speedband if speedband is not None else None,
            "rainfall_mm": rainfall_mm,
            "has_incident": has_inc,
        })
        
        processed += 1
        
        # Log progress every 10 seconds or every 10k links
        current_time = time.time()
        if current_time - last_log_time >= 10.0 or processed % 10000 == 0:
            elapsed = current_time - correlate_start
            rate = processed / elapsed if elapsed > 0 else 0
            remaining = (total_links - processed) / rate if rate > 0 else 0
            print(f"    Progress: {processed}/{total_links} links ({processed*100/total_links:.1f}%) - "
                  f"{rate:.0f} links/s - ETA: {remaining:.0f}s")
            last_log_time = current_time
    
    correlate_elapsed = time.time() - correlate_start
    print(f"    Correlated {processed} links in {correlate_elapsed:.2f}s ({processed/correlate_elapsed:.0f} links/s)")

    # Create DataFrame
    df_start = time.time()
    df = pd.DataFrame(rows)
    df_time = time.time() - df_start
    print(f"  Created DataFrame in {df_time:.2f}s")
    
    # Append to Parquet file
    parquet_start = time.time()
    if os.path.exists(CORRELATED_OUT):
        print("  Reading existing Parquet file...")
        read_start = time.time()
        existing_df = pd.read_parquet(CORRELATED_OUT)
        read_time = time.time() - read_start
        print(f"    Read existing file ({len(existing_df)} rows) in {read_time:.2f}s")
        print("  Concatenating DataFrames...")
        concat_start = time.time()
        df = pd.concat([existing_df, df], ignore_index=True)
        concat_time = time.time() - concat_start
        print(f"    Concatenated in {concat_time:.2f}s")
    
    print("  Writing to Parquet file...")
    write_start = time.time()
    df.to_parquet(CORRELATED_OUT, index=False, engine="pyarrow")
    write_time = time.time() - write_start
    parquet_total = time.time() - parquet_start
    
    file_size_mb = os.path.getsize(CORRELATED_OUT) / (1024 * 1024)
    print(f"  [OK] Wrote Parquet file in {write_time:.2f}s (total I/O: {parquet_total:.2f}s)")
    print(f"  [OK] Appended {len(rows)} rows. Total rows: {len(df)}, File size: {file_size_mb:.2f} MB")
    
    total_cycle_time = time.time() - cycle_start
    print(f"\n  Total cycle time: {total_cycle_time:.2f}s ({total_cycle_time/60:.1f} minutes)")


def main() -> None:
    """Main function with continuous collection loop."""
    print("=" * 60)
    print("Continuous Traffic Data Correlation")
    print("=" * 60)
    print(f"Collection interval: {COLLECTION_INTERVAL} seconds (5 minutes)")
    print(f"Output file: {CORRELATED_OUT}")
    print("Press Ctrl+C to stop")
    print("=" * 60)

    # Load static links data (only once)
    print("\nLoading static links data...")
    with open(LINKS_FILE, "r", encoding="utf-8") as f:
        links = json.load(f)
    print(f"Loaded {len(links)} links")

    # Build geometry (only once)
    link_geom = build_link_geometry(links)
    print(f"Built geometry for {len(link_geom)} links")

    # Fetch rainfall once to create stations file
    print("\nFetching initial rainfall data for station locations...")
    rain_obj = fetch_rainfall()
    save_geometry_files(links, rain_obj)

    # Continuous collection loop
    cycle = 0
    try:
        while True:
            cycle_start_time = time.time()
            cycle += 1
            print(f"\n{'=' * 60}")
            print(f"Collection Cycle #{cycle}")
            print(f"{'=' * 60}")
            
            try:
                collect_and_append(links, link_geom)
            except Exception as e:
                print(f"  [ERROR] Error in collection cycle: {e}")
                import traceback
                traceback.print_exc()
                print("  Continuing to next cycle...")

            # Calculate elapsed time and remaining wait time
            elapsed_time = time.time() - cycle_start_time
            remaining_wait = max(0, COLLECTION_INTERVAL - elapsed_time)
            
            if remaining_wait > 0:
                next_time = time.time() + remaining_wait
                next_str = datetime.fromtimestamp(next_time).strftime("%Y-%m-%d %H:%M:%S")
                print(f"\nCycle completed in {elapsed_time:.1f}s")
                print(f"Next collection at: {next_str}")
                print(f"Waiting {remaining_wait:.1f} seconds...")
                time.sleep(remaining_wait)
            else:
                print(f"\nCycle completed in {elapsed_time:.1f}s (exceeded {COLLECTION_INTERVAL}s interval)")
                print("Starting next cycle immediately...")

    except KeyboardInterrupt:
        print("\n\n" + "=" * 60)
        print("Collection stopped by user")
        print("=" * 60)
        if os.path.exists(CORRELATED_OUT):
            df = pd.read_parquet(CORRELATED_OUT)
            print(f"Final statistics:")
            print(f"  Total rows: {len(df)}")
            print(f"  Unique timestamps: {df['generated_at'].nunique()}")
            print(f"  File size: {os.path.getsize(CORRELATED_OUT) / (1024 * 1024):.2f} MB")
        print("=" * 60)


if __name__ == "__main__":
    main()
