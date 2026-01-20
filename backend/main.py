"""
FastAPI application for real-time bus route statistics.
"""
import json
from fastapi import FastAPI, HTTPException, Query
from typing import Optional
from pydantic import BaseModel

from backend.services.route_service import get_route_links
from backend.services.link_service import get_current_link, get_links_for_analysis
from backend.services.rainfall_service import fetch_rainfall_data, check_rain_in_links
from backend.services.incident_service import fetch_incidents, check_incidents_in_links
from backend.services.speed_service import fetch_speed_bands_for_links
from backend.services.predictor_service import predict_speed
from backend.config import NUM_FUTURE_LINKS

app = FastAPI(title="Bus Route Real-time Stats API", version="1.0.0")


class RealtimeStatsResponse(BaseModel):
    """Response model for realtime_stats endpoint."""
    current_link: dict
    speed_bands: dict
    has_rain: bool
    has_incident: bool
    predicted_speed: float


@app.get("/")
def root():
    """Root endpoint."""
    return {"message": "Bus Route Real-time Stats API", "version": "1.0.0"}


@app.get("/realtime_stats", response_model=RealtimeStatsResponse)
def get_realtime_stats(
    bus_no: int = Query(..., description="Bus service number"),
    direction: int = Query(..., description="Direction (1 or 2)"),
    lat: float = Query(..., description="Current latitude"),
    lon: float = Query(..., description="Current longitude")
):
    """
    Get real-time statistics for a bus route at a given location.
    
    Returns:
        - current_link: The link the bus is currently on
        - speed_bands: Speed band data for inbounds + outbounds of current + next links
        - has_rain: Boolean indicating if there's rain in next few links
        - has_incident: Boolean indicating if there's an incident in next few links
        - predicted_speed: Predicted speed for the next link
    """
    try:
        print(f"[Stage 1] Request received: bus_no={bus_no}, direction={direction}, lat={lat}, lon={lon}")
        # 1. Get route links (cached or fetched)
        print("[Stage 2] Fetching route links...")
        route_data = get_route_links(bus_no, direction)
        if route_data is None:
            print("[Error] Route not found.")
            raise HTTPException(
                status_code=404,
                detail=f"Route not found for bus {bus_no} direction {direction}"
            )

        print(f"[Stage 2] Route data fetched:")
        print(json.dumps({
            "ServiceNo": route_data.get('ServiceNo'),
            "Direction": route_data.get('Direction'),
            "total_links": len(route_data.get('ordered_links', [])),
            "first_link": route_data.get('ordered_links', [{}])[0] if route_data.get('ordered_links') else None
        }, indent=2))
        
        ordered_links = route_data.get('ordered_links', [])
        if not ordered_links:
            print("[Error] No links found for this route.")
            raise HTTPException(
                status_code=404,
                detail=f"No links found for bus {bus_no} direction {direction}"
            )
        
        print("[Stage 3] Identifying current link from coordinates...")
        # 2. Find current link from GPS coordinates
        current_link = get_current_link(lat, lon, ordered_links)
        if current_link is None:
            print("[Error] Could not find current link for GPS coordinates.")
            raise HTTPException(
                status_code=404,
                detail="Could not find current link for given coordinates"
            )
        else:
            print(f"[Info] Found current link: LinkID={current_link.get('LinkID')} Order={current_link.get('order')}")
        
        print("[Stage 4] Getting links for analysis (current + future + inbound/outbounds)...")
        # 3. Get links for analysis (current + next few + inbounds/outbounds)
        links_for_analysis = get_links_for_analysis(
            current_link, route_data, num_future_links=NUM_FUTURE_LINKS
        )
        print(f"[Info] Number of links for analysis: {len(links_for_analysis)}")
        
        print("[Stage 5] Determining next few links (for rain/incident checking)...")
        # 4. Get next few links (for rain/incident checking)
        current_order = current_link.get('order', -1)
        next_links = []
        link_index = route_data.get('link_index', {})
        for i in range(1, NUM_FUTURE_LINKS + 1):
            next_order = current_order + i
            if next_order < len(ordered_links):
                next_link = ordered_links[next_order]
                next_links.append(next_link)
        print(f"[Info] Next {len(next_links)} links determined for rain/incident checks")

        # 4b. Determine which links will be fed into the model history
        # Target link: first next link if available, otherwise current link
        if next_links:
            target_link = next_links[0]
        else:
            target_link = current_link
        target_link_id = str(target_link.get("LinkID", ""))

        model_link_ids = set()

        # Inbound / outbound neighbours of target
        for lid in target_link.get("inbound_link_ids", []) or []:
            if lid:
                model_link_ids.add(str(lid))
        for lid in target_link.get("outbound_link_ids", []) or []:
            if lid:
                model_link_ids.add(str(lid))

        # Current link
        current_link_id = str(current_link.get("LinkID", ""))
        if current_link_id:
            model_link_ids.add(current_link_id)

        # Target link itself
        if target_link_id:
            model_link_ids.add(target_link_id)

        # Next links along the route
        for link in next_links:
            link_id = str(link.get("LinkID", ""))
            if link_id:
                model_link_ids.add(link_id)

        print(f"[Info] Model will use {len(model_link_ids)} link IDs for history.")
        
        # 5. Fetch real-time data
        print("[Stage 6.1] Fetching rainfall data...")
        rainfall_data = fetch_rainfall_data()
        has_rain = check_rain_in_links(next_links, rainfall_data)
        print(f"[Info] Rain present in next links: {has_rain}")
        
        print("[Stage 6.2] Fetching incidents data...")
        incidents_data = fetch_incidents()
        has_incident = check_incidents_in_links(next_links, incidents_data)
        print(f"[Info] Incident present in next links: {has_incident}")
        
        print("[Stage 6.3] Getting link IDs for speed band fetching...")
        # Get link IDs for speed band filtering
        link_ids_for_speed = []
        for link in links_for_analysis:
            link_id = str(link.get('LinkID', ''))
            if link_id:
                link_ids_for_speed.append(link_id)
        print(f"[Info] Need to fetch speed bands for {len(link_ids_for_speed)} link IDs.")
        
        print("[Stage 6.4] Fetching speed bands for needed links (optimized)...")
        # Fetch only the speed bands we need (optimized - stops early once all found)
        speed_bands = fetch_speed_bands_for_links(link_ids_for_speed)
        print(f"[Info] Fetched {len(speed_bands)} speed band records total.")

        # 6.4b. Restrict speed_bands in the response to only those links
        # that are actually used in the model history.
        if model_link_ids:
            original_count = len(speed_bands)
            speed_bands = {
                link_id: data
                for link_id, data in speed_bands.items()
                if link_id in model_link_ids
            }
            print(f"[Info] Filtered speed bands for response from {original_count} to {len(speed_bands)} records (model history links only).")
        
        # 6. Predict speed
        print("[Stage 7] Predicting speed for next link...")
        predicted_speed = predict_speed(
            current_link, next_links, speed_bands, has_rain, has_incident,
            rainfall_data=rainfall_data, links_for_analysis=links_for_analysis
        )
        print(f"[Info] Predicted speed: {predicted_speed}")
        
        # 7. Return response
        print("[Stage 8] Returning response to client.")
        return RealtimeStatsResponse(
            current_link=current_link,
            speed_bands=speed_bands,
            has_rain=has_rain,
            has_incident=has_incident,
            predicted_speed=predicted_speed
        )
    
    except HTTPException:
        print("[HTTPException] Exception raised in endpoint, passing up to FastAPI.")
        raise
    except Exception as e:
        print(f"[Internal Error] {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
