"""
Route loader, validator, and geometric calculator.
Supports multiple coordinate formats (including ZJGroute.txt style)
and provides spherical geodesic calculations.
"""

import os
import json
import math
from typing import List, Tuple, Dict, Any, Optional
from core.coord import convert_coordinates

EARTH_RADIUS = 6371000.0  # Earth radius in meters


def haversine_distance(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """Calculate great-circle distance between two points on Earth in meters."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS * c


def calculate_bearing(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """Calculate the initial bearing (forward azimuth) from point 1 to point 2 in degrees."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lng2 - lng1)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    theta = math.atan2(y, x)
    return (math.degrees(theta) + 360.0) % 360.0


def interpolate_coords(lng1: float, lat1: float, lng2: float, lat2: float, fraction: float) -> Tuple[float, float]:
    """Linear interpolation between two coordinates (accurate for short distances)."""
    fraction = max(0.0, min(1.0, fraction))
    lng = lng1 + (lng2 - lng1) * fraction
    lat = lat1 + (lat2 - lat1) * fraction
    return lng, lat


class RoutePoint:
    """Represents a single waypoint."""

    def __init__(self, lng: float, lat: float):
        self.lng = float(lng)
        self.lat = float(lat)

    def to_tuple(self) -> Tuple[float, float]:
        return self.lng, self.lat

    def __repr__(self):
        return f"RoutePoint(lng={self.lng:.7f}, lat={self.lat:.7f})"


class Route:
    """Loaded route containing waypoints and geometric analysis."""

    def __init__(self, points: List[RoutePoint], source_file: str = ""):
        if len(points) < 2:
            raise ValueError("Route must contain at least 2 points.")
        self.points = points
        self.source_file = source_file
        self._calculate_segments()

    def _calculate_segments(self):
        """Precompute segment distances and cumulative distance."""
        self.segment_distances: List[float] = []
        self.cumulative_distances: List[float] = [0.0]

        total = 0.0
        for i in range(len(self.points) - 1):
            p1 = self.points[i]
            p2 = self.points[i + 1]
            dist = haversine_distance(p1.lng, p1.lat, p2.lng, p2.lat)
            self.segment_distances.append(dist)
            total += dist
            self.cumulative_distances.append(total)

        self.total_length = total
        # Check if closed
        p_first = self.points[0]
        p_last = self.points[-1]
        self.closure_distance = haversine_distance(p_last.lng, p_last.lat, p_first.lng, p_first.lat)
        self.is_closed = self.closure_distance < 30.0

    def close_loop(self):
        """Append the first point to the end if not already closed to form a continuous circuit."""
        if not self.is_closed and self.closure_distance > 1.0:
            self.points.append(RoutePoint(self.points[0].lng, self.points[0].lat))
            self._calculate_segments()

    def convert_coords(self, source_type: str, target_type: str = "wgs84") -> "Route":
        """Return a new Route with coordinates converted between coordinate systems."""
        new_points = []
        for p in self.points:
            c_lng, c_lat = convert_coordinates(p.lng, p.lat, source_type, target_type)
            new_points.append(RoutePoint(c_lng, c_lat))
        return Route(new_points, self.source_file)

    @classmethod
    def load_from_file(cls, filepath: str) -> "Route":
        """Load route from file supporting multiple JSON formats."""
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"Route file not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()

        points = cls._parse_content(content)
        route = cls(points, source_file=filepath)
        route.close_loop()
        return route

    @classmethod
    def _parse_content(cls, content: str) -> List[RoutePoint]:
        """Parse raw content into a list of RoutePoint."""
        # Clean BOM and whitespace
        clean = content.lstrip("\ufeff").strip()

        # If it's comma-separated JSON objects without outer brackets (like ZJGroute.txt)
        if not clean.startswith("["):
            # Ensure wrapped in brackets
            clean = "[" + clean.rstrip(",") + "]"

        try:
            data = json.loads(clean)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse route JSON: {e}")

        points: List[RoutePoint] = []
        for idx, item in enumerate(data):
            if isinstance(item, dict):
                # Check variants of lng / lat
                lng_val = item.get("lng") or item.get("lon") or item.get("longitude") or item.get("x")
                lat_val = item.get("lat") or item.get("latitude") or item.get("y")
                if lng_val is not None and lat_val is not None:
                    points.append(RoutePoint(float(lng_val), float(lat_val)))
                else:
                    raise ValueError(f"Point at index {idx} missing lng/lat fields: {item}")
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                # Format: [lng, lat]
                points.append(RoutePoint(float(item[0]), float(item[1])))
            else:
                raise ValueError(f"Unknown point structure at index {idx}: {item}")

        return points

    def get_summary(self) -> Dict[str, Any]:
        """Return human-readable summary of the route."""
        lons = [p.lng for p in self.points]
        lats = [p.lat for p in self.points]
        return {
            "num_points": len(self.points),
            "total_length_m": round(self.total_length, 2),
            "is_closed": self.is_closed,
            "bbox": {
                "min_lng": min(lons),
                "max_lng": max(lons),
                "min_lat": min(lats),
                "max_lat": max(lats),
            }
        }
