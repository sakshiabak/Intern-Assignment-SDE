"""Small GIS helpers (no external dependencies)."""

import math

EARTH_RADIUS_KM = 6371.0088


def validate_polygon(geom: dict) -> list[list[float]]:
    """Validate a GeoJSON Polygon and return its outer ring."""
    if not isinstance(geom, dict) or geom.get("type") != "Polygon":
        raise ValueError("area must be a GeoJSON Polygon")
    coords = geom.get("coordinates")
    if not coords or not isinstance(coords, list):
        raise ValueError("Polygon needs coordinates")
    ring = coords[0]
    if len(ring) < 4:
        raise ValueError("Polygon ring needs at least 4 positions")
    if ring[0] != ring[-1]:
        raise ValueError("Polygon ring must be closed (first == last)")
    for pos in ring:
        if len(pos) < 2:
            raise ValueError("Each position needs [lon, lat]")
        lon, lat = pos[0], pos[1]
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError(f"Position out of range: {pos}")
    return ring


def bbox(ring: list[list[float]]) -> tuple[float, float, float, float]:
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return min(lons), min(lats), max(lons), max(lats)


def polygon_area_sq_km(ring: list[list[float]]) -> float:
    """Spherical-excess style area for small polygons (Chamberlain-Duquette)."""
    total = 0.0
    for i in range(len(ring) - 1):
        lon1, lat1 = math.radians(ring[i][0]), math.radians(ring[i][1])
        lon2, lat2 = math.radians(ring[i + 1][0]), math.radians(ring[i + 1][1])
        total += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))
    return abs(total * EARTH_RADIUS_KM**2 / 2.0)
