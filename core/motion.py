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
        gps_jitter_meters: float = 0.6,
        lateral_variance_meters: float = 2.2,
        lane_drift_per_lap: bool = True,
        slow_down_on_turns: bool = True,
        interval_sec: float = 1.0,
    ):
        self.route = route
        self.base_speed = max(0.5, float(base_speed_mps))
        self.current_speed = self.base_speed
        self.speed_jitter_pct = max(0.0, min(0.5, float(speed_jitter_pct)))
        self.gps_jitter_meters = max(0.0, float(gps_jitter_meters))
        self.lateral_variance_meters = max(0.0, float(lateral_variance_meters))
        self.lane_drift_per_lap = lane_drift_per_lap
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

        # Speed noise state (mean-reverting process for natural smooth speed curves)
        self._speed_offset = 0.0

        # Lateral dynamics state (2nd-order smooth cross-track wander & cross-lap lane spreading)
        self._lateral_pos = 0.0
        self._lateral_vel = 0.0
        # Initial lap lane tendency (e.g. inside/middle lane)
        self._current_lap_lane = (
            random.uniform(-self.lateral_variance_meters * 0.2, self.lateral_variance_meters * 0.4)
            if self.lane_drift_per_lap else 0.0
        )
        self._target_lap_lane = self._current_lap_lane
        self._last_lateral_m = 0.0

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

    def _apply_lateral_and_gps_jitter(self, clean_lng: float, clean_lat: float, bearing: float) -> Tuple[float, float, float]:
        """
        Apply physically realistic lateral lane wander, cross-lap spreading,
        and GPS sensor multipath noise perpendicular to travel direction.
        Returns: (noisy_lng, noisy_lat, total_lateral_m)
        """
        dt = self.interval_sec

        # 1. Smooth lap-level lane transition (gradually adjust lane tendency over ~15 seconds)
        if self.lane_drift_per_lap:
            alpha = min(1.0, dt / 15.0)
            self._current_lap_lane += alpha * (self._target_lap_lane - self._current_lap_lane)

        # 2. Continuous 2nd-order smooth intra-lap wander (damped spring-mass random walk)
        if self.lateral_variance_meters > 0.01:
            theta_v = 0.15   # Velocity damping
            sigma_v = 0.08   # Acceleration perturbation
            spring_k = 0.015 # Weak restoring force to prevent unbounded divergence

            restoring = -spring_k * self._lateral_pos
            dw = random.gauss(0.0, 1.0)
            self._lateral_vel += (-theta_v * self._lateral_vel + restoring) * dt + sigma_v * dw
            # Limit lateral velocity to realistic human drift (max ~0.25 m/s)
            self._lateral_vel = max(-0.25, min(0.25, self._lateral_vel))
            self._lateral_pos += self._lateral_vel * dt
            # Bound intra-lap position within ±75% of lateral variance
            max_pos = self.lateral_variance_meters * 0.75
            self._lateral_pos = max(-max_pos, min(max_pos, self._lateral_pos))
        else:
            self._lateral_pos = 0.0
            self._lateral_vel = 0.0

        # 3. High-frequency sensor noise (natural micro-jitter)
        hf_lat_noise = random.gauss(0.0, self.gps_jitter_meters * 0.25) if self.gps_jitter_meters > 0 else 0.0
        lon_noise_m = random.gauss(0.0, self.gps_jitter_meters * 0.20) if self.gps_jitter_meters > 0 else 0.0

        # Total lateral offset (perpendicular to heading, positive = right/outer, negative = left/inner)
        total_lateral_m = self._current_lap_lane + self._lateral_pos + hf_lat_noise
        self._last_lateral_m = total_lateral_m

        # 4. Vector projection onto normal and tangent directions
        # Bearing theta is clockwise degrees from North
        rad_b = math.radians(bearing)
        sin_b = math.sin(rad_b)
        cos_b = math.cos(rad_b)

        # Normal vector (right): (cos_b, -sin_b)
        # Tangent vector (forward): (sin_b, cos_b)
        d_east_m = total_lateral_m * cos_b + lon_noise_m * sin_b
        d_north_m = -total_lateral_m * sin_b + lon_noise_m * cos_b

        rad_lat = math.radians(clean_lat)
        d_lat = d_north_m / 111139.0
        d_lng = d_east_m / (111139.0 * math.cos(rad_lat))

        return clean_lng + d_lng, clean_lat + d_lat, total_lateral_m

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
                    if self.lane_drift_per_lap and self.lateral_variance_meters > 0:
                        # Select a new lane target for the new lap (standard 400m track has 8 lanes)
                        # Innermost rail is ~ -0.4*var, outer lanes expand outward (+ to the right)
                        self._target_lap_lane = random.uniform(
                            -self.lateral_variance_meters * 0.4,
                            self.lateral_variance_meters * 1.1,
                        )

        # Interpolate exact point on the current segment
        p1 = self.route.points[self.current_seg_index]
        p2 = self.route.points[self.current_seg_index + 1]
        seg_len = self.route.segment_distances[self.current_seg_index]
        fraction = (self.dist_along_seg / seg_len) if seg_len > 0 else 0.0
        clean_lng, clean_lat = interpolate_coords(p1.lng, p1.lat, p2.lng, p2.lat, fraction)

        bearing = calculate_bearing(p1.lng, p1.lat, p2.lng, p2.lat)

        # Apply lateral dynamics and GPS jitter
        noisy_lng, noisy_lat, lat_offset_m = self._apply_lateral_and_gps_jitter(clean_lng, clean_lat, bearing)

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
            "lateral_offset_m": round(lat_offset_m, 2),
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
