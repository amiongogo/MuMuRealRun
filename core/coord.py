"""
Coordinate conversion module for GPS, GCJ-02 (Mars), and BD-09 (Baidu).
High precision conversion algorithms.
"""

import math
from typing import Tuple

# WGS-84 / Krasovsky 1940 constants
A = 6378245.0  # Semi-major axis
EE = 0.00669342162296594323  # Eccentricity squared


def _out_of_china(lng: float, lat: float) -> bool:
    """Check if coordinates are outside of mainland China."""
    if lng < 72.004 or lng > 137.8347:
        return True
    if lat < 0.8293 or lat > 55.8271:
        return True
    return False


def _transform_lat(lng: float, lat: float) -> float:
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * math.pi) + 20.0 * math.sin(2.0 * lng * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * math.pi) + 40.0 * math.sin(lat / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * math.pi) + 320 * math.sin(lat * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(lng: float, lat: float) -> float:
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * math.pi) + 20.0 * math.sin(2.0 * lng * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * math.pi) + 40.0 * math.sin(lng / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * math.pi) + 300.0 * math.sin(lng / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lng: float, lat: float) -> Tuple[float, float]:
    """Convert WGS-84 (standard GPS) to GCJ-02 (Mars coordinates)."""
    if _out_of_china(lng, lat):
        return lng, lat
    d_lat = _transform_lat(lng - 105.0, lat - 35.0)
    d_lng = _transform_lng(lng - 105.0, lat - 35.0)
    rad_lat = lat / 180.0 * math.pi
    magic = math.sin(rad_lat)
    magic = 1 - EE * magic * magic
    sqrt_magic = math.sqrt(magic)
    d_lat = (d_lat * 180.0) / ((A * (1 - EE)) / (magic * sqrt_magic) * math.pi)
    d_lng = (d_lng * 180.0) / (A / sqrt_magic * math.cos(rad_lat) * math.pi)
    mg_lat = lat + d_lat
    mg_lng = lng + d_lng
    return mg_lng, mg_lat


def gcj02_to_wgs84(lng: float, lat: float) -> Tuple[float, float]:
    """
    Convert GCJ-02 (Mars coordinates, e.g. Amap/Gaode) to WGS-84 (standard GPS).
    Uses iterative refinement for millimeter accuracy.
    """
    if _out_of_china(lng, lat):
        return lng, lat
    curr_lng = lng
    curr_lat = lat
    for _ in range(3):
        mg_lng, mg_lat = wgs84_to_gcj02(curr_lng, curr_lat)
        curr_lng += lng - mg_lng
        curr_lat += lat - mg_lat
    return curr_lng, curr_lat


def bd09_to_gcj02(lng: float, lat: float) -> Tuple[float, float]:
    """Convert Baidu BD-09 to GCJ-02."""
    x = lng - 0.0065
    y = lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * math.pi * 3000.0 / 180.0)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * math.pi * 3000.0 / 180.0)
    gg_lng = z * math.cos(theta)
    gg_lat = z * math.sin(theta)
    return gg_lng, gg_lat


def gcj02_to_bd09(lng: float, lat: float) -> Tuple[float, float]:
    """Convert GCJ-02 to Baidu BD-09."""
    z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * math.pi * 3000.0 / 180.0)
    theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * math.pi * 3000.0 / 180.0)
    bd_lng = z * math.cos(theta) + 0.0065
    bd_lat = z * math.sin(theta) + 0.006
    return bd_lng, bd_lat


def bd09_to_wgs84(lng: float, lat: float) -> Tuple[float, float]:
    """Convert Baidu BD-09 to WGS-84."""
    gcj_lng, gcj_lat = bd09_to_gcj02(lng, lat)
    return gcj02_to_wgs84(gcj_lng, gcj_lat)


def wgs84_to_bd09(lng: float, lat: float) -> Tuple[float, float]:
    """Convert WGS-84 to Baidu BD-09."""
    gcj_lng, gcj_lat = wgs84_to_gcj02(lng, lat)
    return gcj02_to_bd09(gcj_lng, gcj_lat)


def convert_coordinates(lng: float, lat: float, source_type: str, target_type: str = "wgs84") -> Tuple[float, float]:
    """
    General coordinate converter.
    source_type: "gcj02", "wgs84", "bd09"
    target_type: "wgs84", "gcj02", "bd09"
    """
    src = source_type.lower().strip()
    tgt = target_type.lower().strip()
    if src == tgt:
        return lng, lat

    # Step 1: Normalize to WGS-84
    if src == "wgs84":
        w_lng, w_lat = lng, lat
    elif src == "gcj02":
        w_lng, w_lat = gcj02_to_wgs84(lng, lat)
    elif src == "bd09":
        w_lng, w_lat = bd09_to_wgs84(lng, lat)
    else:
        raise ValueError(f"Unsupported source coordinate type: {source_type}")

    # Step 2: Convert from WGS-84 to target
    if tgt == "wgs84":
        return w_lng, w_lat
    elif tgt == "gcj02":
        return wgs84_to_gcj02(w_lng, w_lat)
    elif tgt == "bd09":
        return wgs84_to_bd09(w_lng, w_lat)
    else:
        raise ValueError(f"Unsupported target coordinate type: {target_type}")
