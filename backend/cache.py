"""
Caching logic for route data and speed bands.
"""
from typing import Dict, Any, Optional
import time


class RouteCache:
    """Permanent cache for bus route data."""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def get(self, service_no: int, direction: int) -> Optional[Dict[str, Any]]:
        """Get cached route data."""
        key = f"{service_no}_{direction}"
        return self._cache.get(key)
    
    def set(self, service_no: int, direction: int, route_data: Dict[str, Any]) -> None:
        """Cache route data permanently."""
        key = f"{service_no}_{direction}"
        self._cache[key] = route_data
    
    def has(self, service_no: int, direction: int) -> bool:
        """Check if route is cached."""
        key = f"{service_no}_{direction}"
        return key in self._cache

# Global cache instances
route_cache = RouteCache()
