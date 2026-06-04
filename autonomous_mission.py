"""
Autonomous Mission Planner
Handles GPS waypoint navigation and autonomous mission execution

Manages:
- Waypoint parsing and route planning
- Distance/heading calculations
- Autonomous navigation logic
- Mission state machine
"""

import logging
import math
from dataclasses import dataclass
from typing import List, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class MissionState(Enum):
    """Mission execution states"""
    IDLE = 0
    TAKEOFF = 1
    NAVIGATING = 2
    HOVERING = 3
    LANDING = 4
    COMPLETED = 5
    EMERGENCY = 6


@dataclass
class Waypoint:
    """Single waypoint with GPS coordinates"""
    latitude: float
    longitude: float
    altitude: float = 10.0  # Default 10m
    hold_time: float = 5.0   # Hover time in seconds
    
    def __repr__(self):
        return f"WP(lat={self.latitude:.6f}, lon={self.longitude:.6f}, alt={self.altitude:.1f}m)"


class GPSCalculator:
    """
    GPS math utilities
    Calculates distances and bearings between coordinates
    """
    
    EARTH_RADIUS_M = 6371000  # Earth radius in meters
    
    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate great-circle distance between two GPS coordinates
        
        Args:
            lat1, lon1: Starting coordinate
            lat2, lon2: Target coordinate
        
        Returns:
            Distance in meters
        """
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * \
            math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        
        c = 2 * math.asin(math.sqrt(a))
        distance = GPSCalculator.EARTH_RADIUS_M * c
        
        return distance
    
    @staticmethod
    def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate bearing (direction) from one point to another
        
        Args:
            lat1, lon1: Starting coordinate
            lat2, lon2: Target coordinate
        
        Returns:
            Bearing in degrees (0-360)
        """
        dlon = math.radians(lon2 - lon1)
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        
        x = math.sin(dlon) * math.cos(lat2_rad)
        y = math.cos(lat1_rad) * math.sin(lat2_rad) - \
            math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)
        
        bearing = math.degrees(math.atan2(x, y))
        
        # Normalize to 0-360
        bearing = (bearing + 360) % 360
        
        return bearing
    
    @staticmethod
    def altitude_difference(alt1: float, alt2: float) -> float:
        """Calculate vertical distance between two altitudes"""
        return abs(alt2 - alt1)


class AutonomousMission:
    """
    Main autonomous mission controller
    Orchestrates entire mission from takeoff to landing
    """
    
    def __init__(self, stabilization_controller, sensor_reader, motor_controller):
        """
        Initialize mission planner
        
        Args:
            stabilization_controller: StabilizationController instance
            sensor_reader: SensorReader instance
            motor_controller: MotorController instance
        """
        self.stab = stabilization_controller
        self.sensors = sensor_reader
        self.motors = motor_controller
        
        self.waypoints: List[Waypoint] = []
        self.current_waypoint_idx = 0
        self.mission_state = MissionState.IDLE
        
        # Mission parameters
        self.takeoff_altitude = 10.0  # meters
        self.landing_altitude = 0.5   # meters
        self.waypoint_radius = 2.0    # meters (acceptance radius)
        self.max_speed = 5.0           # m/s
        
        logger.info("Autonomous Mission Planner initialized")
    
    def load_mission(self, waypoints: List[Waypoint]):
        """
        Load waypoints for mission
        
        Args:
            waypoints: List of Waypoint objects
        """
        self.waypoints = waypoints
        self.current_waypoint_idx = 0
        logger.info(f"Mission loaded with {len(waypoints)} waypoints")
        
        for i, wp in enumerate(waypoints):
            logger.info(f"  WP{i}: {wp}")
    
    def load_mission_from_file(self, filename: str):
        """
        Load waypoints from CSV file
        Format: latitude,longitude,altitude,hold_time
        
        Args:
            filename: Path to CSV file
        """
        waypoints = []
        try:
            with open(filename, 'r') as f:
                lines = f.readlines()
                for line in lines[1:]:  # Skip header
                    parts = line.strip().split(',')
                    if len(parts) >= 3:
                        wp = Waypoint(
                            latitude=float(parts[0]),
                            longitude=float(parts[1]),
                            altitude=float(parts[2]),
                            hold_time=float(parts[3]) if len(parts) > 3 else 5.0
                        )
                        waypoints.append(wp)
            
            self.load_mission(waypoints)
            logger.info(f"Mission loaded from {filename}")
        except Exception as e:
            logger.error(f"Failed to load mission file: {e}")
    
    def get_current_waypoint(self) -> Waypoint:
        """Get current target waypoint"""
        if self.current_waypoint_idx < len(self.waypoints):
            return self.waypoints[self.current_waypoint_idx]
        return None
    
    def distance_to_waypoint(self) -> float:
        """Calculate distance to current waypoint"""
        waypoint = self.get_current_waypoint()
        if not waypoint:
            return 0.0
        
        current_pos = self.sensors.state.gps_lat, self.sensors.state.gps_lon
        target_pos = waypoint.latitude, waypoint.longitude
        
        distance = GPSCalculator.haversine_distance(
            current_pos[0], current_pos[1],
            target_pos[0], target_pos[1]
        )
        
        return distance
    
    def bearing_to_waypoint(self) -> float:
        """Calculate bearing to current waypoint"""
        waypoint = self.get_current_waypoint()
        if not waypoint:
            return 0.0
        
        bearing = GPSCalculator.calculate_bearing(
            self.sensors.state.gps_lat,
            self.sensors.state.gps_lon,
            waypoint.latitude,
            waypoint.longitude
        )
        
        return bearing
    
    def altitude_error(self) -> float:
        """Calculate altitude difference from target"""
        waypoint = self.get_current_waypoint()
        if not waypoint:
            return 0.0
        
        error = waypoint.altitude - self.sensors.state.altitude
        return error
    
    def check_waypoint_reached(self) -> bool:
        """
        Check if current waypoint is reached
        Uses acceptance radius (default 2m horizontal)
        """
        distance = self.distance_to_waypoint()
        altitude_error = abs(self.altitude_error())
        
        reached = (distance < self.waypoint_radius and 
                  altitude_error < 1.0)  # 1m altitude tolerance
        
        if reached:
            logger.info(f"Waypoint {self.current_waypoint_idx} reached!")
        
        return reached
    
    def next_waypoint(self):
        """Advance to next waypoint"""
        self.current_waypoint_idx += 1
        logger.info(f"Advancing to waypoint {self.current_waypoint_idx}")
    
    def calculate_attitude_correction(self) -> Tuple[float, float, float]:
        """
        Calculate required attitude (pitch, roll, yaw) to reach waypoint
        
        Returns:
            Tuple of (pitch, roll, yaw) in radians
        """
        bearing = self.bearing_to_waypoint()
        distance = self.distance_to_waypoint()
        altitude_error = self.altitude_error()
        
        # Bearing to required yaw (drone's heading)
        current_yaw = self.sensors.state.yaw
        yaw_error = bearing - math.degrees(current_yaw)
        # Normalize to -180 to 180
        yaw_error = ((yaw_error + 180) % 360) - 180
        yaw_correction = math.radians(yaw_error * 0.01)  # Gentle correction
        
        # Distance to required pitch/roll (forward/sideways movement)
        # Proportional to distance (max 0.3 radians = ~17 degrees tilt)
        max_tilt = 0.3
        tilt_magnitude = min(distance / 50.0, max_tilt)  # Scale by distance
        
        pitch_correction = tilt_magnitude * math.cos(math.radians(bearing))
        roll_correction = tilt_magnitude * math.sin(math.radians(bearing))
        
        # Altitude correction (positive = climb, negative = descend)
        altitude_pid = self.stab.pitch_pid  # Reuse pitch PID for altitude
        altitude_correction = altitude_pid.update(altitude_error) * 0.01
        
        return pitch_correction, roll_correction, yaw_correction
    
    def update_mission(self) -> bool:
        """
        Update mission state machine
        Called continuously during autonomous flight
        
        Returns:
            True if mission is still running, False if completed
        """
        if self.mission_state == MissionState.IDLE:
            return False
        
        elif self.mission_state == MissionState.TAKEOFF:
            # Climb to first waypoint altitude
            altitude_error = self.takeoff_altitude - self.sensors.state.altitude
            if abs(altitude_error) < 0.5:  # Reached takeoff altitude
                logger.info("Takeoff complete, starting navigation")
                self.mission_state = MissionState.NAVIGATING
            
        elif self.mission_state == MissionState.NAVIGATING:
            # Navigate to waypoint
            if self.check_waypoint_reached():
                logger.info(f"Waypoint reached, holding for {self.get_current_waypoint().hold_time}s")
                self.mission_state = MissionState.HOVERING
                self.hover_start_time = 0  # TODO: implement timing
            
        elif self.mission_state == MissionState.HOVERING:
            # Hold at waypoint
            # TODO: Implement hover timer
            # After hold_time expires, go to next waypoint
            self.next_waypoint()
            if self.current_waypoint_idx >= len(self.waypoints):
                logger.info("All waypoints completed, landing")
                self.mission_state = MissionState.LANDING
            else:
                self.mission_state = MissionState.NAVIGATING
        
        elif self.mission_state == MissionState.LANDING:
            # Descend to landing altitude
            altitude_error = self.landing_altitude - self.sensors.state.altitude
            if abs(altitude_error) < 0.3:
                logger.info("Landing complete")
                self.mission_state = MissionState.COMPLETED
                self.motors.disarm_motors()
                return False
        
        elif self.mission_state == MissionState.COMPLETED:
            return False
        
        return True  # Mission still running
    
    def start_mission(self):
        """Begin autonomous mission"""
        if not self.waypoints:
            logger.error("No waypoints loaded")
            return False
        
        logger.info("Starting autonomous mission")
        self.mission_state = MissionState.TAKEOFF
        self.current_waypoint_idx = 0
        return True
    
    def abort_mission(self):
        """Emergency abort - land immediately"""
        logger.warning("Mission aborted - landing now")
        self.mission_state = MissionState.LANDING
        self.motors.disarm_motors()
    
    def get_mission_status(self) -> dict:
        """Get current mission status"""
        waypoint = self.get_current_waypoint()
        
        return {
            'state': self.mission_state.name,
            'waypoint_index': self.current_waypoint_idx,
            'total_waypoints': len(self.waypoints),
            'current_waypoint': str(waypoint),
            'distance_to_waypoint': self.distance_to_waypoint(),
            'bearing_to_waypoint': self.bearing_to_waypoint(),
            'current_altitude': self.sensors.state.altitude,
            'gps_satellites': self.sensors.state.gps_satellites
        }


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Create sample waypoints (Stanford campus area)
    waypoints = [
        Waypoint(latitude=37.4274, longitude=-122.1695, altitude=10.0),
        Waypoint(latitude=37.4275, longitude=-122.1690, altitude=15.0),
        Waypoint(latitude=37.4280, longitude=-122.1685, altitude=12.0),
        Waypoint(latitude=37.4274, longitude=-122.1695, altitude=10.0),  # Return home
    ]
    
    logger.info("Example mission waypoints:")
    for i, wp in enumerate(waypoints):
        logger.info(f"  WP{i}: {wp}")
    
    # Calculate distances between waypoints
    logger.info("\nDistances between waypoints:")
    for i in range(len(waypoints) - 1):
        dist = GPSCalculator.haversine_distance(
            waypoints[i].latitude, waypoints[i].longitude,
            waypoints[i+1].latitude, waypoints[i+1].longitude
        )
        logger.info(f"  WP{i} → WP{i+1}: {dist:.1f}m")
