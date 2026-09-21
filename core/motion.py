"""
Realistic human runner motion simulation engine.
Simulates physiological speed fluctuations, realistic GPS jitter/multipath,
turn decelerations, and smooth continuous polyline progression.
"""

import math
import random
from typing import Tuple, Optional, Dict, Any
from core.route import Route, RoutePoint, haversine_distance, calculate_bearing, interpolate_coords, EARTH_RADIUS


class MotionSimulator:
    """Simulates realistic human running along a route."""

    def __init__(
        self,
        route: Route,
        base_speed_mps: float = 3.2,
        speed_jitter_pct: float = 0.10,
        gps_jitter_meters: float = 0.8,
        slow_down_on_turns: bool = True,
        interval_sec: float = 1.0,
    ):
        self.route = route
        self.base_speed = max(0.5, float(base_speed_mps))
        self.current_speed = self.base_speed
        self.speed_jitter_pct = max(0.0, min(0.5, float(speed_jitter_pct)))
        self.gps_jitter_meters = max(0.0, float(gps_jitter_meters))
        self.slow_down_on_turns = slow_down_on_turns
        self.interval_sec = max(0.1, float(interval_sec))

        # Position tracking along the route
        self.current_seg_index = 0
        self.dist_along_seg = 0.0  # meters along current segment

        # Statistics
        self.total_distance_traveled = 0.0
        self.total_elapsed_time = 0.0
        self.lap_count = 1
        self.total_steps = 0

        # Noise state (mean-reverting process for natural smooth speed curves)
        self._speed_offset = 0.0

        # Current coordinate
        p0 = self.route.points[0]
        self.current_lng = p0.lng
        self.current_lat = p0.lat

    def _update_speed(self, turn_angle: float) -> float:
        """
        Calculates instantaneous speed using an Ornstein-Uhlenbeck process
        combined with corner deceleration.
        """
        # Mean reversion theta and diffusion sigma
        theta = 0.3
        sigma = self.base_speed * self.speed_jitter_pct * 0.4
        dt = self.interval_sec

        # Random walk with momentum
        dw = random.gauss(0.0, math.sqrt(dt))
        self._speed_offset += -theta * self._speed_offset * dt + sigma * dw

        # Bound the speed fluctuation
        max_offset = self.base_speed * self.speed_jitter_pct
        self._speed_offset = max(-max_offset, min(max_offset, self._speed_offset))

        instant_speed = self.base_speed + self._speed_offset

        # Decelerate on sharp turns (e.g. angle > 30 degrees)
        if self.slow_down_on_turns and turn_angle > 30.0:
            turn_factor = max(0.70, 1.0 - (turn_angle / 180.0) * 0.35)
            instant_speed *= turn_factor

        self.current_speed = max(0.5, instant_speed)
        return self.current_speed

    def _get_turn_angle(self, seg_idx: int) -> float:
        """Calculate turning angle between current segment and next segment."""
        num_pts = len(self.route.points)
        if seg_idx >= num_pts - 1:
            return 0.0

        p1 = self.route.points[seg_idx]
        p2 = self.route.points[seg_idx + 1]
        b1 = calculate_bearing(p1.lng, p1.lat, p2.lng, p2.lat)

        next_idx = (seg_idx + 1) % (num_pts - 1)
        p3 = self.route.points[next_idx + 1]
        b2 = calculate_bearing(p2.lng, p2.lat, p3.lng, p3.lat)

        diff = abs(b2 - b1)
        if diff > 180.0:
            diff = 360.0 - diff
        return diff

    def _apply_gps_jitter(self, lng: float, lat: float, bearing: float) -> Tuple[float, float]:
        """Apply tiny natural GPS multipath noise perpendicular to travel direction."""
        if self.gps_jitter_meters <= 0.001:
            return lng, lat

        # Lateral jitter (perpendicular) + longitudinal jitter (along movement)
        lat_noise_m = random.gauss(0.0, self.gps_jitter_meters * 0.7)
        lon_noise_m = random.gauss(0.0, self.gps_jitter_meters * 0.4)

        # Convert meters offset to latitude and longitude delta
        # 1 deg lat ≈ 111,139 m
        # 1 deg lng ≈ 111,139 * cos(lat) m
        rad_lat = math.radians(lat)
        d_lat = lat_noise_m / 111139.0
        d_lng = lon_noise_m / (111139.0 * math.cos(rad_lat))

        return lng + d_lng, lat + d_lat

    def step(self) -> Dict[str, Any]:
        """
        Advance the simulation by one time interval.
        Returns the new state dict with coordinates, speed, pace, and progress.
        """
        turn_angle = self._get_turn_angle(self.current_seg_index)
        speed = self._update_speed(turn_angle)
        step_distance = speed * self.interval_sec

        # Advance along the route segments
        dist_to_move = step_distance
        num_segs = len(self.route.points) - 1

        while dist_to_move > 0:
            current_seg_len = self.route.segment_distances[self.current_seg_index]
            remaining_in_seg = current_seg_len - self.dist_along_seg

            if dist_to_move < remaining_in_seg:
                self.dist_along_seg += dist_to_move
                dist_to_move = 0.0
            else:
                dist_to_move -= remaining_in_seg
                self.dist_along_seg = 0.0
                self.current_seg_index += 1

                # If reached end of route, wrap around to start
                if self.current_seg_index >= num_segs:
                    self.current_seg_index = 0
                    self.lap_count += 1

        # Interpolate exact point on the current segment
        p1 = self.route.points[self.current_seg_index]
        p2 = self.route.points[self.current_seg_index + 1]
        seg_len = self.route.segment_distances[self.current_seg_index]
        fraction = (self.dist_along_seg / seg_len) if seg_len > 0 else 0.0
        clean_lng, clean_lat = interpolate_coords(p1.lng, p1.lat, p2.lng, p2.lat, fraction)

        bearing = calculate_bearing(p1.lng, p1.lat, p2.lng, p2.lat)

        # Apply natural GPS jitter
        noisy_lng, noisy_lat = self._apply_gps_jitter(clean_lng, clean_lat, bearing)

        self.current_lng = noisy_lng
        self.current_lat = noisy_lat
        self.total_distance_traveled += step_distance
        self.total_elapsed_time += self.interval_sec

        # Simulate steps (cadence: 160-185 spm depending on speed)
        # stride length ≈ 0.45 * height + 0.2 * speed ≈ 0.9 + 0.1 * speed
        stride = 0.90 + 0.12 * (speed - 2.5)
        new_steps = int(round(step_distance / max(0.6, stride)))
        self.total_steps += new_steps

        # Calculate current pace (minutes:seconds per km)
        pace_sec_per_km = (1000.0 / speed) if speed > 0 else 0
        pace_min = int(pace_sec_per_km // 60)
        pace_sec = int(pace_sec_per_km % 60)
        pace_str = f"{pace_min}'{pace_sec:02d}\""

        # Calculate overall average speed
        avg_speed_mps = self.total_distance_traveled / self.total_elapsed_time if self.total_elapsed_time > 0 else 0.0
        avg_pace_sec = (1000.0 / avg_speed_mps) if avg_speed_mps > 0 else 0
        avg_pace_str = f"{int(avg_pace_sec // 60)}'{int(avg_pace_sec % 60):02d}\""

        return {
            "lng": self.current_lng,
            "lat": self.current_lat,
            "raw_lng": clean_lng,
            "raw_lat": clean_lat,
            "speed_mps": speed,
            "speed_kmh": speed * 3.6,
            "pace_str": pace_str,
            "avg_pace_str": avg_pace_str,
            "total_distance_m": self.total_distance_traveled,
            "total_elapsed_sec": self.total_elapsed_time,
            "lap": self.lap_count,
            "steps": self.total_steps,
            "seg_index": self.current_seg_index,
            "bearing": bearing,
        }
