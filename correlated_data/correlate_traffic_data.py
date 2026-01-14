import json
import math
import os
from datetime import datetime
from typing import Any, Dict, List, Tuple


ROOT_DIR = os.path.dirname(os.path.abspath(os.path.join(__file__, os.pardir)))

LINKS_FILE = os.path.join(ROOT_DIR, "speed_bands", "data", "links.json")
SPEED_FILE = os.path.join(ROOT_DIR, "speed_bands", "data", "traffic_speed_data_13Jan_15_00.json")
RAINFALL_FILE = os.path.join(ROOT_DIR, "rainfall", "data", "rainfall_data.json")
INCIDENTS_FILE = os.path.join(ROOT_DIR, "traffic_incident", "data", "traffic_incidents.json")

OUT_DIR = os.path.dirname(__file__)
LINK_GEOMETRY_OUT = os.path.join(OUT_DIR, "link_geometry.json")
RAINFALL_STATIONS_OUT = os.path.join(OUT_DIR, "rainfall_stations.json")
CORRELATED_OUT = os.path.join(OUT_DIR, "correlated_traffic_data.json")


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


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
    # Convert to radians for projection
    phi = math.radians(lat)
    x = math.radians(lon)
    x1 = math.radians(lon1)
    x2 = math.radians(lon2)
    y = math.radians(lat)
    y1 = math.radians(lat1)
    y2 = math.radians(lat2)

    # Equirectangular projection (x * cos(phi), y)
    def proj(xx: float, yy: float) -> Tuple[float, float]:
        return (xx * math.cos(phi), yy)

    px, py = proj(x, y)
    p1x, p1y = proj(x1, y1)
    p2x, p2y = proj(x2, y2)

    dx = p2x - p1x
    dy = p2y - p1y
    if dx == 0 and dy == 0:
        # Segment is a point
        return haversine_km(lat, lon, lat1, lon1)

    # Project point onto segment, clamp t to [0,1]
    t = ((px - p1x) * dx + (py - p1y) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x = p1x + t * dx
    proj_y = p1y + t * dy

    # Convert back to lat/lon approx
    proj_lon = math.degrees(proj_x / math.cos(phi))
    proj_lat = math.degrees(proj_y)
    return haversine_km(lat, lon, proj_lat, proj_lon)


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


def build_rainfall_stations(rain_obj: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, float], str]:
    """
    Return:
      stations: {station_id: {latitude, longitude, name}}
      readings: {station_id: rainfall_mm}
      timestamp: truncated timestamp string
    """
    data = rain_obj.get("data", {})
    meta = data.get("metadata", {})
    items = data.get("items", [])

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
    rain_ts_raw = None
    if items:
        item0 = items[0]
        rain_ts_raw = item0.get("timestamp")
        for r in item0.get("readings", []):
            sid = r.get("station_id")
            val = r.get("value")
            if sid is None or val is None:
                continue
            try:
                readings[sid] = float(val)
            except (TypeError, ValueError):
                continue

    rain_ts = truncate_ts(rain_ts_raw) if rain_ts_raw else None
    return stations, readings, rain_ts or ""


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


def build_speed_snapshot(speed_data: Dict[str, List[Dict[str, Any]]]) -> Tuple[Dict[str, Dict[str, Any]], str]:
    """
    For each link, take the latest observation (by timestamp string).
    Returns:
      snapshot: {LinkID: {speedband, timestamp_truncated}}
      global_timestamp: latest timestamp overall (truncated)
    """
    snapshot: Dict[str, Dict[str, Any]] = {}
    latest_ts_raw = None

    for link_id, observations in speed_data.items():
        if not observations:
            continue
        # Choose observation with max timestamp string (ISO sortable)
        obs = max(observations, key=lambda o: o.get("timestamp", ""))
        speedband = obs.get("speedband")
        ts_raw = obs.get("timestamp")
        if ts_raw:
            if latest_ts_raw is None or ts_raw > latest_ts_raw:
                latest_ts_raw = ts_raw
        if speedband is None or ts_raw is None:
            continue
        snapshot[str(link_id)] = {
            "speedband": speedband,
            "timestamp": truncate_ts(ts_raw),
        }

    global_ts = truncate_ts(latest_ts_raw) if latest_ts_raw else ""
    return snapshot, global_ts


def build_incident_index(inc_obj: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    """Return list of incidents with lat/lon/message and retrieval timestamp."""
    ts_raw = inc_obj.get("timestamp")
    data = inc_obj.get("data", {})
    incidents = data.get("value", []) if isinstance(data, dict) else []
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
    return cleaned, truncate_ts(ts_raw) if ts_raw else ""


def link_has_incident(
    link_id: str,
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

    # No road-name match: fall back to distance
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


def main() -> None:
    # Load base data
    print("Loading links.json ...")
    links = load_json(LINKS_FILE)
    print(f"Loaded {len(links)} links")

    print("Loading speed band time series ...")
    speed_data = load_json(SPEED_FILE)

    print("Loading rainfall data ...")
    rain_obj = load_json(RAINFALL_FILE)

    print("Loading traffic incidents ...")
    inc_obj = load_json(INCIDENTS_FILE)

    # Build geometry & stations, and save them separately
    print("Building link geometry reference ...")
    link_geom = build_link_geometry(links)
    save_json(LINK_GEOMETRY_OUT, link_geom)
    print(f"Saved link geometry for {len(link_geom)} links to {LINK_GEOMETRY_OUT}")

    print("Building rainfall stations reference ...")
    stations, readings, rain_ts = build_rainfall_stations(rain_obj)
    save_json(RAINFALL_STATIONS_OUT, stations)
    print(f"Saved {len(stations)} rainfall stations to {RAINFALL_STATIONS_OUT}")

    # Build snapshots
    print("Building latest speed band snapshot ...")
    speed_snapshot, speed_global_ts = build_speed_snapshot(speed_data)

    print("Preparing incidents ...")
    incidents, inc_ts = build_incident_index(inc_obj)

    # Correlate
    print("Correlating data per link ...")
    correlated_links: List[Dict[str, Any]] = []

    for link in links:
        link_id = str(link.get("LinkID"))
        if link_id not in link_geom:
            continue

        geom = link_geom[link_id]
        road_name = geom.get("RoadName") or link.get("RoadName") or ""

        # Speed band (may be missing for some links)
        sb = speed_snapshot.get(link_id)

        # Rainfall from nearest station
        rainfall_mm = find_nearest_station_rainfall(geom, stations, readings)

        # Incident flag
        has_inc = link_has_incident(link_id, geom, road_name, incidents)

        entry: Dict[str, Any] = {
            "LinkID": link_id,
            "speed_band": sb if sb is not None else None,
            "rainfall": {
                "rainfall_mm": rainfall_mm,
                "timestamp": rain_ts,
            },
            "traffic_incidents": {
                "has_incident": has_inc,
                "timestamp": inc_ts,
            },
        }
        correlated_links.append(entry)

    correlated = {
        "metadata": {
            "speed_band_timestamp": speed_global_ts,
            "rainfall_timestamp": rain_ts,
            "traffic_incident_timestamp": inc_ts,
            "total_links": len(correlated_links),
            "generated_at": truncate_ts(datetime.now().isoformat()),
        },
        "links": correlated_links,
    }

    save_json(CORRELATED_OUT, correlated)
    print(f"Saved correlated data for {len(correlated_links)} links to {CORRELATED_OUT}")


if __name__ == "__main__":
    main()

